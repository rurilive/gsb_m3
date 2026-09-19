"""KVStore：预写日志之上的小型 KV 视图。"""

from .wal import WriteAheadLog


class KVStore:
    """set/get 直连内存视图，日志负责持久化。"""

    def __init__(self, directory, max_segment_bytes: int = 1 << 20):
        self._wal = WriteAheadLog(directory, max_segment_bytes)
        self._data = {}

    def set(self, key, value) -> None:
        self._data[key] = value
        self._wal.append({"op": "set", "key": key, "value": value})

    def delete(self, key) -> None:
        self._data.pop(key, None)
        self._wal.append({"op": "del", "key": key})

    def get(self, key):
        return self._data.get(key)

    def recover(self) -> int:
        """重放日志重建内存视图，返回恢复的记录数。"""
        applied = 0
        for rec in self._wal.replay():
            if rec.get("op") == "set":
                self._data[rec["key"]] = rec["value"]
            elif rec.get("op") == "del":
                self._data.pop(rec["key"], None)
            applied += 1
        return applied

    def checkpoint(self) -> None:
        self._wal.checkpoint()

    def close(self) -> None:
        self._wal.close()
