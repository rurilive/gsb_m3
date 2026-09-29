"""quory: 最朴素的副本写入库，写向全部副本广播并等待全体成功后返回。"""

from .writer import WriteAll

__all__ = ["WriteAll"]
