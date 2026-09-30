"""treediam: 树统计工具的朴素基线（改造前）。

对外只暴露 Tree 与那一层朴素统计，以及错误基类。
"""

from .tree import (
    DiameterError,
    ForestError,
    Tree,
    all_distance_sums,
    all_distances,
    center,
    centroid,
    components,
    diameter,
    diameter_path,
    distance_sum,
    eccentricity_max,
    farthest_distance,
    farthest_from,
    in_same_root,
    is_tree,
    max_distance_sum_point,
    pair_distance_sum,
    reachable_from,
)

__all__ = [
    "Tree",
    "DiameterError",
    "ForestError",
    "in_same_root",
    "reachable_from",
    "is_tree",
    "farthest_from",
    "all_distances",
    "diameter",
    "diameter_path",
    "farthest_distance",
    "eccentricity_max",
    "distance_sum",
    "all_distance_sums",
    "max_distance_sum_point",
    "pair_distance_sum",
    "components",
    "center",
    "centroid",
]
