"""Small demo for the bitrange package.

The first block exercises the current baseline (flat per-bit scanning).  The
second block is a placeholder for the interval-tree work described in the task.
"""

from bitrange import FlatBits


def baseline_demo():
    bits = FlatBits(16)
    for index in range(2, 8):
        bits.set(index)
    print("baseline all-one in [2, 8):", bits.is_all_one(2, 8))
    print("baseline all-one in [2, 9):", bits.is_all_one(2, 9))
    print("baseline ones in [0, 16):", bits.count_all_one())
    print("baseline next zero from 3:", bits.find_next_zero(3))


# TODO(区间树改造): 补充一轮区间置位与找零演示。


if __name__ == "__main__":
    baseline_demo()
