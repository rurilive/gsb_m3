"""幂等键存储：按幂等键记住已处理请求的结果。

上游提交前先用幂等键问一遍要不要干活，干完把结果记回键上；同一个键再
提交时直接把上次的结果回放出去，避免重复扣款。时间读取统一走注入的
clock；记录可以落一份到磁盘，进程重启后接着用。纯标准库实现。
"""

import json
import os
import tempfile
import threading
import time


class TruncatedResult:
    """结果超过体积上限时留下的截断标记。

    真正的结果没有进缓存，只留下这个标记：下游取回时用 isinstance 即可
    认出“这单的结果被截断过”，并可通过 original_size 知道原始体积。
    preview 是原结果序列化文本的开头一小段，方便人工对账辨认。
    """

    __slots__ = ("original_size", "limit", "preview")

    def __init__(self, original_size, limit, preview=None):
        self.original_size = original_size
        self.limit = limit
        self.preview = preview

    def __eq__(self, other):
        if not isinstance(other, TruncatedResult):
            return NotImplemented
        return (
            self.original_size == other.original_size
            and self.limit == other.limit
            and self.preview == other.preview
        )

    def __repr__(self):
        return (
            "TruncatedResult(original_size={}, limit={}, preview={!r})".format(
                self.original_size, self.limit, self.preview
            )
        )

    def to_dict(self):
        return {
            "__idemkey_truncated__": True,
            "original_size": self.original_size,
            "limit": self.limit,
            "preview": self.preview,
        }

    @classmethod
    def from_dict(cls, item):
        return cls(item["original_size"], item["limit"], item.get("preview"))


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


def _is_truncated_marker(item):
    return isinstance(item, dict) and item.get("__idemkey_truncated__") is True


class IdempotencyStore:
    """按幂等键记住请求结果的存储。

    ttl: 记录存活秒数，从请求完成时刻起算；None 表示永不过期。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    path: 落盘文件路径；None 表示只放在内存里。
    max_result_size: 结果序列化后的字节上限（UTF-8），超出则只存一份
        TruncatedResult 截断标记；None 表示不限制。
    """

    def __init__(
        self, ttl=None, clock=time.monotonic, path=None, max_result_size=None
    ):
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive")
        if max_result_size is not None and max_result_size <= 0:
            raise ValueError("max_result_size must be positive")
        self._ttl = ttl
        self._clock = clock
        self._path = path
        self._max_result_size = max_result_size
        self._lock = threading.Lock()
        self._records = {}
        if path is not None:
            self._load()

    # -- 对外接口 --

    def begin(self, key):
        """提交前问一句这个键要不要干活。

        返回 True 表示该由本次请求处理；返回 False 表示这个键已经处理过，
        调用方应当改用 get(key) 取回上次的结果。
        """
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            self._purge(now)
            record = self._records.get(key)
            if record is not None:
                return False
            # 先把键占上，免得同一个键并发送进来跑两遍
            self._records[key] = _Record(None, now, None)
            self._save()
            return True

    def finish(self, key, result):
        """把处理结果记到键上，这个键之后就算已处理。"""
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            record = self._records.get(key)
            result = self._truncate_if_needed(result)
            if record is None:
                self._records[key] = _Record(result, now, now)
            else:
                record.result = result
                record.finished_at = now
            self._save()
            return result

    def fail(self, key):
        """处理中途失败时释放键上的占位，允许同一键重新提交。

        只清理“占了键但还没收尾”的记录；已经 finish 的结果不受影响。
        返回 True 表示占位被释放，False 表示没有可释放的占位。
        """
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            self._purge(now)
            record = self._records.get(key)
            if record is None or record.finished_at is not None:
                return False
            del self._records[key]
            self._save()
            return True

    def renew(self, key):
        """以当前时刻为键的有效期续期。

        处理中的占位按“重新开工”续期，避免长流程跑到一半过期；已经
        finish 的记录按“重新完成”续期，从现在起再活一个 ttl。
        返回 True 表示键存在且已续期，False 表示键不存在（可能已过期）。
        """
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return False
            record.created_at = now
            if record.finished_at is not None:
                record.finished_at = now
            self._save()
            return True

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
        """键的规范化：只去首尾空白，保留原始大小写（大小写不同即不同键）。"""
        return key.strip()

    def _purge(self, now):
        """清掉已经过期的记录。"""
        if self._ttl is None:
            return
        expired = [
            key
            for key, record in self._records.items()
            if now - self._expiry_base(record) >= self._ttl
        ]
        for key in expired:
            del self._records[key]

    @staticmethod
    def _expiry_base(record):
        """过期判定的起算时刻：收过尾的按完成时刻，没收尾的按开工时刻。"""
        if record.finished_at is not None:
            return record.finished_at
        return record.created_at

    def _truncate_if_needed(self, result):
        """结果超体积上限时换成截断标记，避免撑爆缓存。"""
        if self._max_result_size is None:
            return result
        try:
            encoded = json.dumps(result, ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError):
            return result
        if len(encoded) <= self._max_result_size:
            return result
        preview = None
        head = encoded[: self._max_result_size]
        head = head.decode("utf-8", errors="ignore")
        if head:
            preview = head
        return TruncatedResult(len(encoded), self._max_result_size, preview)

    def _load(self):
        """从磁盘读回上次的记录。"""
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        for key, item in raw.items():
            result = item["result"]
            if _is_truncated_marker(result):
                result = TruncatedResult.from_dict(result)
            self._records[key] = _Record(
                result, item["created_at"], item["finished_at"]
            )
        # begin() 占上但进程崩在 finish() 之前的占位不能让它永久卡住：
        # 重启即视为这次处理没发生，同一键可以重新提交。
        stale = [
            key
            for key, record in self._records.items()
            if record.finished_at is None
        ]
        for key in stale:
            del self._records[key]
        if stale:
            self._save()

    def _save(self):
        """把当前记录写到磁盘。"""
        if self._path is None:
            return
        raw = {
            key: {
                "result": self._encode_result(record.result),
                "created_at": record.created_at,
                "finished_at": record.finished_at,
            }
            for key, record in self._records.items()
        }
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        # 同目录临时文件 + os.replace，避免写到一半崩溃留下半截 JSON。
        fd, tmp_name = tempfile.mkstemp(
            dir=directory or ".", prefix=".idemkey-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(raw, fh, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self._path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    @staticmethod
    def _encode_result(result):
        if isinstance(result, TruncatedResult):
            return result.to_dict()
        return result
