"""walog 自有异常类型。

预写日志里可诊断的错误都在这里定义，全部继承 WalogError，调用方只捕捉
WalogError 即可一次性接住所有错误。条目校验、截断越界、序号非法相关的错误
留待后续在这一层扩展。
"""


class WalogError(Exception):
    """walog 所有可诊断错误的基类。"""


class InvalidLsn(WalogError):
    """序号非法：非整数、为负或超出当前可接受的范围。"""


class TruncateError(WalogError):
    """截断被拒：目标序号不合法，例如指向未来的、还没有写入的位置。"""


class CorruptEntry(WalogError):
    """条目损坏：校验和不匹配，重放时在最后一条完好条目处停下。"""
