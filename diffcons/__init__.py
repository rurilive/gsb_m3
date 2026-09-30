"""diffcons: 差分约束系统的可行解求解器。"""

from diffcons.system import (
    Constraint,
    ConstraintError,
    DiffError,
    DifferenceSystem,
    Infeasible,
)

__all__ = [
    "Constraint",
    "ConstraintError",
    "DiffError",
    "DifferenceSystem",
    "Infeasible",
]
