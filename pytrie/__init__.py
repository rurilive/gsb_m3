"""pytrie: 纯标准库的字符串词表。

当前只提供基于列表线性扫描的 WordList，作为前缀树改造前的基线。
"""

from pytrie.trie import WordList

__all__ = ["WordList"]
