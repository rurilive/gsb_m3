"""quotatree 的异常类型。"""


class QuotaError(Exception):
    """配额管理相关错误的基类。"""


class UnknownTeam(QuotaError):
    """操作了没注册过的团队。"""
