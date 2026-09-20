"""预写日志：追加记录、组提交落盘、按 LSN 顺序重放。

磁盘格式固定为 [lsn:8 大端][长度:4 大端][payload]，一条紧接一条。
append 返回就代表这条记录已经 fsync 到盘，调用方可以放心去改内存。
末尾若残留写了一半的记录（进程中途被杀），打开时会被截掉。

并发下的 append 由后台刷盘线程攒批：一批记录一次 write + 一次 fsync，
整批一起应答；刷盘失败时批内（以及之后所有）append 都拿到同一个异常。
"""
import os
import struct
import threading
import time

_HEAD = struct.Struct(">QI")
HEAD_SIZE = _HEAD.size

# 组提交参数：批太大延迟变差，太小省不下几次 fsync。
_MAX_BATCH_RECORDS = 256   # 一批最多多少条
_MAX_BATCH_BYTES = 1 << 20  # 一批最多多少字节
_LINGER_SECONDS = 0.002    # 只有上一批打满了，才肯为攒下一批多等这么久


def _iter_records(path):
    """顺序读出所有完整记录，碰到残尾就停。"""
    with open(path, "rb") as f:
        while True:
            head = f.read(HEAD_SIZE)
            if len(head) < HEAD_SIZE:
                return
            lsn, size = _HEAD.unpack(head)
            payload = f.read(size)
            if len(payload) < size:
                return
            yield lsn, payload


def _scan(path):
    """返回 (最后一条完整记录的 LSN, 有效字节数)；空文件是 (0, 0)。"""
    last = 0
    valid = 0
    for lsn, payload in _iter_records(path):
        last = lsn
        valid += HEAD_SIZE + len(payload)
    return last, valid


class WriteAheadLog:
    """单文件 WAL。同一个文件同一时刻只应由一个实例负责写。"""

    def __init__(self, path):
        self._path = path
        if os.path.exists(path):
            self._last_lsn, valid = _scan(path)
            if valid != os.path.getsize(path):
                os.truncate(path, valid)
        else:
            self._last_lsn = 0
        self._fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
        self._cond = threading.Condition()
        self._pending = []          # [(lsn, 记录字节)]，等待落盘的一批
        self._pending_bytes = 0
        self._durable_lsn = self._last_lsn
        self._error = None          # 刷盘失败后置位，WAL 不可用
        self._closed = False
        self._hot = False           # 上一批是否打满（决定要不要 linger）
        self._flusher = threading.Thread(
            target=self._flush_loop, name="walg-flusher", daemon=True)
        self._flusher.start()

    def append(self, payload):
        """追加一条记录，返回它分到的 LSN；返回时该记录已经落盘。"""
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("payload 必须是 bytes")
        record = bytes(payload)
        with self._cond:
            if self._closed:
                raise ValueError("WAL 已关闭")
            if self._error is not None:
                raise self._error
            lsn = self._last_lsn + 1
            self._last_lsn = lsn
            self._pending.append((lsn, _HEAD.pack(lsn, len(record)) + record))
            self._pending_bytes += HEAD_SIZE + len(record)
            self._cond.notify_all()
            while self._durable_lsn < lsn and self._error is None:
                self._cond.wait()
            if self._durable_lsn < lsn:
                raise self._error
            return lsn

    def _flush_loop(self):
        """后台刷盘：攒一批 -> 一次 write -> 一次 fsync -> 唤醒整批。"""
        while True:
            with self._cond:
                while not self._pending and not self._closed:
                    self._cond.wait()
                if not self._pending:
                    return  # 已关闭且队列排空
                if self._hot:
                    self._linger_locked()
                batch = self._pending
                last_lsn = batch[-1][0]
                batch_bytes = self._pending_bytes
                self._pending = []
                self._pending_bytes = 0
                self._hot = (len(batch) >= _MAX_BATCH_RECORDS
                             or batch_bytes >= _MAX_BATCH_BYTES)
            try:
                self._write_all(b"".join(rec for _, rec in batch))
                os.fsync(self._fd)
            except OSError as exc:
                with self._cond:
                    self._error = exc
                    self._cond.notify_all()
                return
            with self._cond:
                self._durable_lsn = last_lsn
                self._cond.notify_all()

    def _linger_locked(self):
        """高峰期（上一批打满）稍等片刻，让这一批也攒大一点。"""
        deadline = time.monotonic() + _LINGER_SECONDS
        while (not self._closed
               and len(self._pending) < _MAX_BATCH_RECORDS
               and self._pending_bytes < _MAX_BATCH_BYTES):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            self._cond.wait(remaining)

    def _write_all(self, buf):
        while buf:
            buf = buf[os.write(self._fd, buf):]

    def read_from(self, lsn=1):
        """按 LSN 升序重放，返回所有 >= lsn 的完整记录。"""
        return [(l, p) for l, p in _iter_records(self._path) if l >= lsn]

    @property
    def last_lsn(self):
        return self._last_lsn

    def close(self):
        with self._cond:
            if self._closed:
                return
            self._closed = True
            self._cond.notify_all()
        self._flusher.join()
        os.close(self._fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
