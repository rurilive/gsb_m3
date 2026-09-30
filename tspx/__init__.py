"""tspx：完全图上最短闭合回路的朴素工具（改造前基线）。"""

from .tour import TspSolver, distance, tour_length

__all__ = ["TspSolver", "distance", "tour_length"]
