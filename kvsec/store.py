"""本地键值存储，主数据落在目录下的一个追加文件里。

内存里只留主键到文件位置的目录，取记录时按位置读回；
put 覆盖写、delete 删除，都追加一条新记录，旧版本留在文件里。
打开时重放数据文件重建目录与序号，末尾写了一半的记录就地截掉。
"""

import os
import threading

from .codec import RecordCorrupt, decode_line, encode_line

DATA_FILE = "data.log"


def _check_key(key):
    if not isinstance(key, str) or not key or any(ch.isspace() for ch in key):
        raise ValueError("主键必须是非空且不含空白的字符串: %r" % (key,))
    return key


class KVStore:
    """按主键读写记录的本地库。

    record 是 dict。put 覆盖写，delete 删掉，两者都会同步通知
    subscribe 进来的回调，回调收到 (key, old, new)，删除时 new 为 None，
    old 是覆盖前的旧记录（原本没有则为 None）。删不存在的主键不通知。
    """

    def __init__(self, path):
        self.path = os.path.abspath(path)
        os.makedirs(self.path, exist_ok=True)
        self._data_path = os.path.join(self.path, DATA_FILE)
        self._lock = threading.RLock()
        self._keydir = {}
        self._seq = 0
        self._subscribers = []
        self._puts = 0
        self._deletes = 0
        self._gets = 0
        self._scans = 0
        self._appender = open(self._data_path, "ab")  # 不存在则建空文件
        self._read = open(self._data_path, "rb")
        try:
            self._replay()
        except Exception:
            self.close()
            raise

    # 收尾与生命周期

    def close(self):
        """关掉文件句柄。关掉之后再调其他方法会抛 ValueError。"""
        with self._lock:
            if not self._read.closed:
                self._read.close()
            if not self._appender.closed:
                self._appender.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _ensure_open(self):
        if self._read.closed:
            raise ValueError("store 已关闭")

    # 读写

    def put(self, key, record):
        """写入或覆盖一条记录，返回本次的序号。"""
        key = _check_key(key)
        if not isinstance(record, dict):
            raise TypeError("record 必须是 dict: %r" % (record,))
        with self._lock:
            self._ensure_open()
            old = self.get(key) if self._subscribers else None
            self._seq += 1
            data = encode_line(self._seq, "P", key, record)
            offset = self._append(data)
            self._keydir[key] = (offset, len(data))
            self._puts += 1
            for callback in list(self._subscribers):
                callback(key, old, dict(record))
            return self._seq

    def delete(self, key):
        """删除一条记录，返回是否真的删掉了。"""
        key = _check_key(key)
        with self._lock:
            self._ensure_open()
            if key not in self._keydir:
                return False
            old = self.get(key)
            self._seq += 1
            self._append(encode_line(self._seq, "D", key, {}))
            del self._keydir[key]
            self._deletes += 1
            for callback in list(self._subscribers):
                callback(key, old, None)
            return True

    def get(self, key):
        """取一条记录，不存在返回 None。返回的是独立副本。"""
        with self._lock:
            self._ensure_open()
            pos = self._keydir.get(key)
            if pos is None:
                return None
            offset, length = pos
            self._read.seek(offset)
            line = self._read.read(length)
            self._gets += 1
        try:
            _, _, _, record = decode_line(line)
        except RecordCorrupt:
            return None
        return record

    def keys(self):
        """全部主键，排序列表。"""
        with self._lock:
            self._ensure_open()
            return sorted(self._keydir)

    def scan(self):
        """全量扫描，按主键排序返回全部 (key, record)，取每条主键的最新版本。"""
        with self._lock:
            self._ensure_open()
            self._scans += 1
            latest = {}
            with open(self._data_path, "rb") as fh:
                while True:
                    line = fh.readline()
                    if not line:
                        break
                    try:
                        _, op, key, record = decode_line(line)
                    except RecordCorrupt:
                        break
                    if op == "P":
                        latest[key] = record
                    else:
                        latest.pop(key, None)
            return [(key, latest[key]) for key in sorted(latest)]

    # 通知与观测

    def subscribe(self, callback):
        """登记写入回调，put/delete 返回前在当前线程里同步调用。"""
        with self._lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback):
        """注销回调，返回是否注销掉了。"""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)
                return True
            return False

    def sequence(self):
        """当前序号，每次 put/delete 加一，重放后等于文件里最后一条的序号。"""
        with self._lock:
            return self._seq

    def stats(self):
        """计数快照，返回独立 dict。"""
        with self._lock:
            return {
                "keys": len(self._keydir),
                "puts": self._puts,
                "deletes": self._deletes,
                "gets": self._gets,
                "scans": self._scans,
                "sequence": self._seq,
            }

    # 内部

    def _append(self, data):
        self._appender.seek(0, os.SEEK_END)
        offset = self._appender.tell()
        self._appender.write(data)
        self._appender.flush()
        return offset

    def _replay(self):
        """重放数据文件，重建主键目录与序号，撞上损坏记录就截尾。"""
        good_end = 0
        with open(self._data_path, "rb") as fh:
            while True:
                offset = fh.tell()
                line = fh.readline()
                if not line:
                    break
                try:
                    seq, op, key, record = decode_line(line)
                except RecordCorrupt:
                    break
                if seq != self._seq + 1:
                    break
                self._seq = seq
                good_end = offset + len(line)
                if op == "P":
                    self._keydir[key] = (offset, len(line))
                else:
                    self._keydir.pop(key, None)
        with open(self._data_path, "r+b") as fh:
            fh.truncate(good_end)
