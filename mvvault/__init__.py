"""mvvault: 单机版本化内存 KV，写入按提交时间戳留版，纯标准库。"""

from .store import MVStore, Version

__all__ = ["MVStore", "Version"]
