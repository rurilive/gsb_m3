"""幂等键存储：按幂等键记住已处理请求的结果。

上游提交前先用幂等键问一遍要不要干活，干完把结果记回键上；同一个键再
提交时直接把上次的结果回放出去，避免重复扣款。时间读取统一走注入的
clock；记录可以落一份到磁盘，进程重启后接着用。纯标准库实现。
"""

import json
import os
import threading
import time


class _Record:
    """一条幂等记录。

    result 为 None 表示键已经占上但结果还没写回来；finished_at 为 None
    表示这次处理还没收尾。
    """

    __slots__ = ("result", "created_at", "finished_at")

    def __init__(self, result, created_at, finished_at):
        self.result = result
        self.created_at = created_at
        self.finished_at = finished_at


class IdempotencyStore:
    """按幂等键记住请求结果的存储。

    ttl: 记录存活秒数，从请求完成时刻起算；None 表示永不过期。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    path: 落盘文件路径；None 表示只放在内存里。
    """

    def __init__(self, ttl=None, clock=time.monotonic, path=None):
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive")
        self._ttl = ttl
        self._clock = clock
        self._path = path
        self._lock = threading.Lock()
        self._records = {}
        if path is not None:
            self._load()

    # -- 对外接口 --

    def begin(self, key):
        """提交前问一句这个键要不要干活。

        返回 True 表示该由本次请求处理；返回 False 表示这个键已经处理过，
        调用方应当改用 get(key) 取回上次的结果。

        键被占上但一直没收尾（上次处理中途失败）时，视为可以重试，返回
        True 让本次请求接手。
        """
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            self._purge(now)
            record = self._records.get(key)
            if record is not None and record.finished_at is not None:
                return False
            # 把键占上；上一次占键没收尾的，这里由本次请求重新占上
            self._records[key] = _Record(None, now, None)
            self._save()
            return True

    def finish(self, key, result):
        """把处理结果记到键上，这个键之后就算已处理。"""
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            record = self._records.get(key)
            if record is None:
                self._records[key] = _Record(result, now, now)
            else:
                record.result = result
                record.finished_at = now
            self._save()
            return result

    def get(self, key):
        """取这个键已经记下的结果，没有就返回 None。"""
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            self._purge(now)
            record = self._records.get(key)
            if record is None:
                return None
            return record.result

    # -- 内部实现 --

    def _normalize(self, key):
        """键的规范化：只去掉首尾空白。

        大小写不同的键是不同的键，不能归并，否则只差大小写的两个单号
        会被当成同一笔。
        """
        return key.strip()

    def _purge(self, now):
        """清掉已经过期的记录。

        已收尾的记录从收尾时刻起算 ttl；没收尾的从占键时刻起算。
        """
        if self._ttl is None:
            return
        expired = [
            key
            for key, record in self._records.items()
            if now - self._expiry_base(record) >= self._ttl
        ]
        for key in expired:
            del self._records[key]
        if expired:
            self._save()

    @staticmethod
    def _expiry_base(record):
        """过期起算时刻：收过尾的按收尾时刻，否则按占键时刻。"""
        if record.finished_at is not None:
            return record.finished_at
        return record.created_at

    def _load(self):
        """从磁盘读回上次的记录。"""
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        for key, item in raw.items():
            self._records[key] = _Record(
                item["result"], item["created_at"], item["finished_at"]
            )

    def _save(self):
        """把当前记录写到磁盘。"""
        if self._path is None:
            return
        raw = {
            key: {
                "result": record.result,
                "created_at": record.created_at,
                "finished_at": record.finished_at,
            }
            for key, record in self._records.items()
        }
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(raw, fh)
