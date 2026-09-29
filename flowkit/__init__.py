"""flowkit：一个纯标准库的工作流状态机引擎。

当前对外能力是 Machine：注册状态与转移、用 step 沿转移推进、并保留推进路径。
守卫与动作、子状态机嵌套、历史态与冲突检测都留待在这个基础上补齐。
"""

from .errors import DefinitionError, FlowError, InvalidTransition, TransitionConflict
from .machine import Machine

__all__ = [
    "DefinitionError",
    "FlowError",
    "InvalidTransition",
    "Machine",
    "TransitionConflict",
]
