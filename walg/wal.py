"""预写日志：追加记录、组提交落盘、按 LSN 顺序重放。

磁盘格式固定为 [lsn:8 大端][长度:4 大端][payload]，一条紧接一条。
append 返回就代表这条记录已经 fsync 到盘，调用方可以放心去改内存。
末尾若残留写了一半的记录（进程中途被杀），打开时会被截掉。

内部由一个写线程把并发 append 攒成一批：同批记录只做一次 write+fsync，
所有调用方在刷盘完成后才被唤醒；刷盘失败则整批一起失败。
"""
import os
import struct
import threading
import time

_HEAD = struct.Struct(">QI")
HEAD_SIZE = _HEAD.size

DEFAULT_BATCH_SIZE = 128
DEFAULT_BATCH_BYTES = 256 * 1024
DEFAULT_GROUP_WAIT = 0.002


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

    def __init__(self, path, batch_size=DEFAULT_BATCH_SIZE,
                 batch_bytes=DEFAULT_BATCH_BYTES, group_wait=DEFAULT_GROUP_WAIT):
        self._path = path
        self._batch_size = batch_size
        self._batch_bytes = batch_bytes
        self._group_wait = group_wait
        self._cond = threading.Condition()
        self._io_lock = threading.Lock()
        self._pending = []
        self._broken = None
        self._closing = False
        if os.path.exists(path):
            self._last_lsn, valid = _scan(path)
            if valid != os.path.getsize(path):
                os.truncate(path, valid)
        else:
            self._last_lsn = 0
        self._fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
        self._thread = threading.Thread(target=self._run, name="wal-writer")
        self._thread.daemon = True
        self._thread.start()

    def append(self, payload):
        """追加一条记录，返回它分到的 LSN；返回时该记录已经落盘。"""
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("payload 必须是 bytes")
        item = [bytes(payload), threading.Event(), None, None]
        with self._cond:
            if self._broken is not None:
                raise self._broken
            if self._closing:
                raise OSError("WAL 已关闭")
            self._pending.append(item)
            self._cond.notify()
        item[1].wait()
        if item[2] is not None:
            raise item[2]
        return item[3]

    def _write_all(self, buf):
        while buf:
            buf = buf[os.write(self._fd, buf):]

    def _collect_batch(self):
        """在写线程中取出一批，等待由条件变量驱动，不忙等。"""
        with self._cond:
            while not self._pending:
                if self._closing or self._broken is not None:
                    return None
                self._cond.wait()
            if self._broken is not None:
                return None
            # leader 留一个 group_wait 宽限窗口，把并发到达的请求凑进同一批。
            # notify 只用于提前结束等待（凑满、关闭、故障）；没凑满就睡到 deadline。
            deadline = time.monotonic() + self._group_wait
            total = len(self._pending[0][0]) + HEAD_SIZE
            while (len(self._pending) < self._batch_size
                   and total < self._batch_bytes
                   and not self._closing and self._broken is None):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._cond.wait(remaining)
                total = sum(len(item[0]) + HEAD_SIZE for item in self._pending)
            if self._broken is not None:
                return None
            take, size_total = 0, 0
            while take < len(self._pending) and take < self._batch_size:
                size = len(self._pending[take][0]) + HEAD_SIZE
                if take > 0 and size_total + size > self._batch_bytes:
                    break
                size_total += size
                take += 1
            batch = self._pending[:take]
            del self._pending[:take]
            return batch

    def _flush(self, batch):
        """按入队顺序分配 LSN，一次 write 一次 fsync 落整批。"""
        buf = bytearray()
        lsn = self._last_lsn
        for item in batch:
            lsn += 1
            item[3] = lsn
            buf += _HEAD.pack(lsn, len(item[0])) + item[0]
        with self._io_lock:
            self._write_all(buf)
            os.fsync(self._fd)
        self._last_lsn = lsn

    def _fail_batch(self, batch, error):
        """整批同成败：所有等待方拿到同一个错误。"""
        with self._cond:
            if self._broken is None:
                self._broken = error
            wake = batch + self._pending
            self._pending = []
        for item in wake:
            item[2] = error
            item[1].set()

    def _run(self):
        while True:
            batch = self._collect_batch()
            if batch is None:
                return
            try:
                self._flush(batch)
            except OSError as error:
                self._fail_batch(batch, error)
                continue
            for item in batch:
                item[1].set()

    def read_from(self, lsn=1):
        """按 LSN 升序重放，返回所有 >= lsn 的完整记录。"""
        with self._io_lock:
            return [(l, p) for l, p in _iter_records(self._path) if l >= lsn]

    @property
    def last_lsn(self):
        return self._last_lsn

    def close(self):
        with self._cond:
            if self._closing:
                return
            self._closing = True
            self._cond.notify_all()
        self._thread.join()
        with self._io_lock:
            os.close(self._fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
