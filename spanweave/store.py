"""采集缓冲：按到达顺序吃进记录，按 trace 分组交给 builder。

采集端是并发上报的，记录可以分多批 feed 进来，同一个 span_id 可能因为
重试被上报多次。父 span 可能比子 span 晚到，缓冲阶段不做父子判断，
全部先入册，挂树交给 builder 统一处理。
"""

from .builder import build_trees
from .model import Span


class SpanStore:
    """到达顺序不定、可能重传的 span 缓冲。

    所有到达的 span 都先入册（含父还没到的），去重只看 span_id；
    最终的父子关系在 ``traces()`` 重建时统一确定，因此同一份数据
    无论分多少批、按什么顺序 feed，重建结果都一致。
    """

    def __init__(self):
        self._seen = set()   # 已入册的 span_id，重传只留先到的一条
        self._by_trace = {}  # trace_id -> [Span]

    def feed(self, records):
        """吃进一批记录（可分批、可迭代器），重复 span_id 只留先到的。"""
        for record in records:
            span = Span.from_record(record)
            if span.span_id in self._seen:
                continue
            self._seen.add(span.span_id)
            self._by_trace.setdefault(span.trace_id, []).append(span)

    def traces(self):
        """把缓冲里的 span 重建为调用树，trace 按 trace_id 排序。"""
        return build_trees(self._by_trace)
