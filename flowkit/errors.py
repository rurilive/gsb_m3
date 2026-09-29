"""flowkit 自有异常类型。

状态机在构造、注册与推进过程中出现的可诊断错误都在这里定义，全部继承
FlowError，调用方只捕捉 FlowError 即可一次性接住所有状态机错误。
"""


class FlowError(Exception):
    """状态机所有可诊断错误的基类。"""


class DefinitionError(FlowError):
    """定义期错误：转移指向未知状态、同名状态重复注册等。"""


class InvalidTransition(FlowError):
    """推进期错误：当前状态上没有通往目标状态的合法转移。"""


class TransitionConflict(FlowError):
    """推进期错误：同一状态出发有多条转移同时可用，去向不唯一。"""
