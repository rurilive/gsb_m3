"""dlx: 精确覆盖问题的朴素求解工具（改造前基线）。"""

from .core import (
    Erro,
    MatrixError,
    ShapeError,
    column_coverage,
    conflict_columns,
    is_exact_cover,
    minimum_solution,
    search_steps,
    solution_count,
    solve,
    solve_all,
)

__all__ = [
    "solve",
    "solve_all",
    "minimum_solution",
    "solution_count",
    "is_exact_cover",
    "column_coverage",
    "conflict_columns",
    "search_steps",
    "Erro",
    "ShapeError",
    "MatrixError",
]
