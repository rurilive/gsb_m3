"""lfukit：按访问频次淘汰的 LFU 缓存，纯标准库。"""

from .cache import LFUCache

__all__ = ["LFUCache"]
