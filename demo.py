"""bmsearch 现状演示。

第一段：朴素实现——对文本的每个对齐位置从前往后逐字符比对，失配即把窗口整体
右移一位重来，据此给出全部出现位置、出现次数、是否出现，并暴露每个对齐点的
字符比较与位移次数，以及长文本上与朴素比较次数的规模关系。
第二段：预留的坏字符与好后缀两条启发式匹配演示位子（见文末注释）。
"""

from bmsearch import BmSearch


def main():
    print("=== 朴素逐位对齐查找结果 ===")
    kit = BmSearch("aabaabaab")
    print(f"  模式 -> {kit.pattern()}")
    print(f"  在文本中的全部起始位置 -> {kit.find_occurrences('aabaabaabaab')}")
    print(f"  出现次数 -> {kit.count_occurrences('aabaabaabaab')}")
    print(f"  是否出现 -> {kit.contains('aabaabaabaab')}")
    print(f"  逐次匹配信息 -> {kit.match_steps()}")
    print(f"  字符比较总次数 -> {kit.search_steps()}")
    print(f"  窗口位移总次数 -> {kit.search_jumps()}")

    print("--- 全相同字符文本上的退化观察 ---")
    kit2 = BmSearch("aaaa")
    print(f"  全部起始位置 -> {kit2.find_occurrences('a' * 12)}")
    print(f"  字符比较总次数 -> {kit2.search_steps()}")

    print("--- 长文本上朴素比较次数随长度增长的规模 ---")
    kit3 = BmSearch("abab")
    for n in (20, 60, 180):
        text = "ab" * n
        print(f"  文本长度 {len(text)} -> 朴素比较 {kit3.naive_comparisons(text)}")

    # TODO: 第二段演示（实现后补）
    # 用坏字符规则表与好后缀规则表（含好后缀位移表与边界位移表）实现 BM 匹配，
    # 失配时取两条规则给出的较大右移量，再以前缀函数独立求出现位置与 BM 路逐项
    # 印证，两路不许互相调用。实现后在这里加一段演示：用同一批串跑坏字符与好后缀
    # 两路启发式，打印全部出现位置、出现次数、是否出现、每次匹配的跳转与比较次数，
    # 并与上面的朴素结果逐项对照，同时暴露朴素比较次数与 BM 比较次数的规模分层。


if __name__ == "__main__":
    main()
