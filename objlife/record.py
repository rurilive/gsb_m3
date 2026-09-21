"""对象记录：容器里每个活对象一条。"""


class Record:
    """一个活对象的全部记账。

    count 是总引用数：外部引用（create 与 retain 给的）加上所有入边。
    ext 是外部引用数，link 进来的边不算在内。
    out_links 是这个对象持有强引用的对象，按连边先后排列。
    """

    __slots__ = ("oid", "kind", "payload", "out_links", "count", "ext")

    def __init__(self, oid, kind, payload):
        self.oid = oid
        self.kind = kind
        self.payload = payload
        self.out_links = []
        self.count = 1  # create 交给调用方的那一份引用
        self.ext = 1

    def __repr__(self):
        return "Record(oid=%d, kind=%r, count=%d, ext=%d)" % (
            self.oid, self.kind, self.count, self.ext)
