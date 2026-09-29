"""nearbex 演示脚本。

第一段演示基线能力：逐字符比较两个文本的差异数。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nearbex import CharDiff


def demo_baseline():
    print("== 基线：逐字符比较 ==")
    pairs = [
        ("hello world", "hello world"),
        ("hello world", "hallo world"),
        ("kitten", "sitting"),
    ]
    for left, right in pairs:
        diff = CharDiff(left, right)
        print(
            "left=", left,
            "right=", right,
            "diff_count=", diff.diff_count(),
            "is_same=", diff.is_same(),
        )


def demo_fingerprint_search():
    # TODO(指纹改造): 在此补一轮指纹与近似检索演示，
    # 包括文本指纹、指纹间的海明距离与相似度，以及分段索引在给定
    # 海明距离阈值下召回的全部近似项，并演示一批文本的聚类去重结果。
    pass


if __name__ == "__main__":
    demo_baseline()
    demo_fingerprint_search()
