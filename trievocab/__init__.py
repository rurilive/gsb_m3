"""trievocab: 字符串词表与前缀统计。

当前只提供一份只支持线性扫描的 FlatVocab, 作为字典树改造前的基线。
"""

from trievocab.vocab import (
    EmptyError,
    FlatVocab,
    NotFoundError,
    VocabError,
)

__all__ = ["FlatVocab", "VocabError", "EmptyError", "NotFoundError"]
