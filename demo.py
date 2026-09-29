"""Small runnable demo for treaplib.

The first section exercises the current array-backed path.  The second
section is a placeholder for the tree-backed path and is filled in once
that path exists.
"""

from treaplib.seq import ListLike


def first_section():
    print("现在这一段跑的是改造前的朴素数组路径。")
    seq = ListLike([1, 2, 3, 4, 5])
    print("初始内容:", seq.snapshot())

    seq.insert(2, 99)
    print("在下标二之前插入之后:", seq.snapshot())

    seq.erase(0)
    print("删掉首元素之后:", seq.snapshot())

    seq.reverse_range(1, 4)
    print("翻转中间一段之后:", seq.snapshot())

    taken = seq.splice(0, 2)
    print("切走的一段:", taken)
    print("切走之后:", seq.snapshot())

    print("长度:", len(seq))
    return seq


def second_section():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    first_section()
    second_section()
    print("演示结束。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
