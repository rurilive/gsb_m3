"""ledgerbook 自有异常类型。

所有可诊断错误继承 LedgerError，便于调用方一次性兜住。现状只用到金额相关的
一类错误；科目、借贷平衡、期间与冲销相关的错误留待后续在这一层扩展。
"""


class LedgerError(Exception):
    """账本所有可诊断错误的基类。"""


class InvalidAmount(LedgerError):
    """金额不合法：非整数分、为零或为负。"""
