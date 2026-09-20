"""预写日志：追加记录、同步落盘、按 LSN 顺序重放。

磁盘格式固定为 [lsn:8 大端][长度:4 大端][payload]，一条紧接一条。
append 返回就代表这条记录已经 fsync 到盘，调用方可以放心去改内存。
末尾若残留写了一半的记录（进程中途被杀），打开时会被截掉。
"""
import os
import struct
import threading

_HEAD = struct.Struct(">QI")
HEAD_SIZE = _HEAD.size


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
        self._lock = threading.Lock()
        if os.path.exists(path):
            self._last_lsn, valid = _scan(path)
            if valid != os.path.getsize(path):
                os.truncate(path, valid)
        else:
            self._last_lsn = 0
        self._fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)

    def append(self, payload):
        """追加一条记录，返回它分到的 LSN；返回时该记录已经落盘。"""
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("payload 必须是 bytes")
        with self._lock:
            lsn = self._last_lsn + 1
            self._write_all(_HEAD.pack(lsn, len(payload)) + bytes(payload))
            os.fsync(self._fd)
            self._last_lsn = lsn
            return lsn

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
        os.close(self._fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
