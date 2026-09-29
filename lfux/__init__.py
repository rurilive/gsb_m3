"""lfux：一个纯标准库的定容缓存包。

眼下只提供最朴素的定容缓存 FifoCache：容量固定，内部用一个字典存键值，
满的时候按插入先后淘汰最早插入的那一条，完全不看访问频次。
"""

from .cache import FifoCache

__all__ = ["FifoCache"]
