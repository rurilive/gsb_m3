"""采集缓冲：按到达顺序吃进记录，按 trace 分组交给 builder。

采集端是并发上报的，记录可以分多批 feed 进来，同一个 span_id 可能因为
重试被上报多次。子 span 比父 span 先到也不打紧：缓冲一条都不丢，挂树
时 builder 会把后到的父补上，始终不来的父交给 Tree.unresolved。
"""

from .builder import build_trees
from .model import Span


class SpanStore:
    """到达顺序不定、可能重传的 span 缓冲。所有记录都先入册。"""

    def __init__(self):
        self._by_id = {}  # span_id -> Span，判重，重传只留先到的一条

    def feed(self, records):
        """按到达顺序吃进一批记录，重复的 span_id 只留先到的一条。"""
        for record in records:
            span = Span.from_record(record)
            if span.span_id in self._by_id:
                continue
            self._by_id[span.span_id] = span

    def traces(self):
        """把缓冲里的 span 重建为调用树，trace 按 trace_id 排序。"""
        by_trace = {}
        for span in self._by_id.values():
            by_trace.setdefault(span.trace_id, []).append(span)
        return build_trees(by_trace)
