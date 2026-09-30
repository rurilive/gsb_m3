"""bipmatch 现状演示。

第一段：朴素最大匹配——在一张固定图上跑改造前的朴素匹配器，
        看匹配边数与匹配边集，并演示自环被拒。
第二段：预留的升级演示位子（见文末注释）。
"""

from bipmatch.matcher import NaiveMatcher, SelfLoopError


def main():
    print("=== 朴素最大匹配（现有能力） ===")
    m = NaiveMatcher(["a", "b", "c"], ["x", "y", "z"])
    m.add_edge("a", "x")
    m.add_edge("a", "y")
    m.add_edge("b", "y")
    m.add_edge("c", "z")
    print(f"  left_nodes()      -> {m.left_nodes()}")
    print(f"  right_nodes()     -> {m.right_nodes()}")
    print(f"  edges()           -> {m.edges()}")
    print(f"  match()           -> {m.match()}")
    print(f"  matching_edges()  -> {m.matching_edges()}")

    try:
        bad = NaiveMatcher(["v"], ["v"])
        bad.add_edge("v", "v")
    except SelfLoopError as exc:
        print(f"  自环被拒            -> {exc}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
