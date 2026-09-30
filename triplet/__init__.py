"""triplet: 整数序列上的上升三元组统计工具集（当前为基线朴素实现）。"""

from triplet.naive import (
    InvalidInputError,
    InvalidLengthError,
    TripletAnalysis,
    TripletError,
    count_increasing_subseq_of_length_naive,
    count_increasing_triplets_naive,
    count_non_decreasing_triplets_naive,
    enumerate_triplet_trials,
    first_increasing_triplet_naive,
    has_increasing_triplet_naive,
)

__all__ = [
    "InvalidInputError",
    "InvalidLengthError",
    "TripletAnalysis",
    "TripletError",
    "count_increasing_subseq_of_length_naive",
    "count_increasing_triplets_naive",
    "count_non_decreasing_triplets_naive",
    "enumerate_triplet_trials",
    "first_increasing_triplet_naive",
    "has_increasing_triplet_naive",
]
