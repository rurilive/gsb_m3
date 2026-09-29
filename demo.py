"""Small demo for the commitx package.

The first block exercises the current baseline (single-node commit).  The
second block is a placeholder for the two-phase commit work described in the
task.
"""

from commitx import LocalCommit


def baseline_demo():
    c = LocalCommit()
    c.apply({"key": "account:a", "value": 100})
    c.apply({"key": "account:b", "value": 50})
    print("baseline keys:", c.keys())
    print("baseline read account:a:", c.read("account:a"))


# TODO(两阶段提交改造): 补充一轮投票提交与中止回滚的演示。


if __name__ == "__main__":
    baseline_demo()
