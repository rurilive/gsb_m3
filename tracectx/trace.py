"""跨线程调用链上下文：correlation-id 传播、span 嵌套计时、树形汇总报告。

入口用 start_trace() 开一条链路（生成 correlation-id）；span(name) 开一段
计时，嵌套的 span 自动挂到当前 span 下。TracedThread 与
TracedThreadPoolExecutor 把当前链路上下文带进新线程，跨线程的 span 依然
归位到同一棵树；并发链路之间互不串号。收尾用 format_report() /
print_report() 一次打出整棵树，超过慢阈值的 span 带 [SLOW] 标记。
"""

import contextlib
import contextvars
import functools
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

__all__ = [
    "Span",
    "TracedThread",
    "TracedThreadPoolExecutor",
    "current_correlation_id",
    "format_report",
    "get_slow_threshold",
    "print_report",
    "set_slow_threshold",
    "span",
    "start_trace",
]

_current_trace = contextvars.ContextVar("tracectx_current_trace", default=None)
_current_span = contextvars.ContextVar("tracectx_current_span", default=None)

_slow_threshold = 0.5  # 秒，模块级默认慢阈值


def set_slow_threshold(seconds):
    """设置模块级默认慢阈值（秒），对之后开始的链路生效。"""
    global _slow_threshold
    if seconds < 0:
        raise ValueError("slow threshold must be >= 0")
    _slow_threshold = float(seconds)


def get_slow_threshold():
    """返回当前模块级默认慢阈值（秒）。"""
    return _slow_threshold


def current_correlation_id():
    """返回当前链路的 correlation-id；不在任何链路里时返回 None。"""
    trace = _current_trace.get()
    return trace.correlation_id if trace is not None else None


class _Trace:
    """一条链路的共享状态：id、慢阈值、根 span 列表。"""

    def __init__(self, correlation_id, slow_threshold):
        self.correlation_id = correlation_id
        self.slow_threshold = slow_threshold
        self.roots = []
        self.lock = threading.Lock()

    def add_root(self, node):
        with self.lock:
            self.roots.append(node)


class Span:
    """一段命名计时：monotonic 计时，子 span 挂在 children 下。"""

    def __init__(self, name, parent, trace, threshold):
        self.name = name
        self.parent = parent
        self.trace = trace
        self.threshold = threshold
        self.children = []
        self.started_at = None
        self.duration = None
        self._lock = threading.Lock()

    def add_child(self, child):
        with self._lock:
            self.children.append(child)

    def snapshot_children(self):
        with self._lock:
            return list(self.children)

    @property
    def slow(self):
        """耗时超过链路慢阈值则为 True；未结束的 span 不算慢。"""
        return self.duration is not None and self.duration > self.threshold


@contextlib.contextmanager
def start_trace(correlation_id=None, slow_threshold=None):
    """开一条调用链：生成（或沿用给定的）correlation-id，退出时还原。

    slow_threshold 缺省用模块级默认（见 set_slow_threshold）。
    """
    cid = correlation_id or uuid.uuid4().hex[:12]
    threshold = _slow_threshold if slow_threshold is None else float(slow_threshold)
    token = _current_trace.set(_Trace(cid, threshold))
    try:
        yield cid
    finally:
        _current_trace.reset(token)


@contextlib.contextmanager
def span(name):
    """开一段命名计时；嵌套时挂到当前 span 下，否则记为链路根 span。"""
    trace = _current_trace.get()
    parent = _current_span.get()
    threshold = trace.slow_threshold if trace is not None else _slow_threshold
    node = Span(name, parent, trace, threshold)
    if parent is not None:
        parent.add_child(node)
    elif trace is not None:
        trace.add_root(node)
    token = _current_span.set(node)
    node.started_at = time.monotonic()
    try:
        yield node
    finally:
        node.duration = time.monotonic() - node.started_at
        _current_span.reset(token)


def _format_span(node, depth, lines):
    if node.duration is None:
        timing = "running"
    else:
        timing = "%.1fms" % (node.duration * 1000.0)
    marker = " [SLOW]" if node.slow else ""
    lines.append("%s%s %s%s" % ("  " * depth, node.name, timing, marker))
    for child in node.snapshot_children():
        _format_span(child, depth + 1, lines)


def format_report():
    """把当前链路的 span 树格式化成缩进文本（需在 start_trace 内调用）。"""
    trace = _current_trace.get()
    if trace is None:
        raise RuntimeError("format_report() requires an active trace")
    lines = [
        "trace %s (slow>%.3fs)" % (trace.correlation_id, trace.slow_threshold)
    ]
    with trace.lock:
        roots = list(trace.roots)
    for root in roots:
        _format_span(root, 0, lines)
    return "\n".join(lines)


def print_report(file=None):
    """把当前链路的 span 树一次打印出来（默认 stdout）。"""
    print(format_report(), file=file)


class TracedThread(threading.Thread):
    """threading.Thread 包装：启动时把当前链路上下文带进新线程。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._inherited_ctx = contextvars.copy_context()

    def run(self):
        self._inherited_ctx.run(super().run)


class TracedThreadPoolExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor 包装：submit 的任务携带提交时的链路上下文。"""

    def submit(self, fn, *args, **kwargs):
        ctx = contextvars.copy_context()
        return super().submit(functools.partial(ctx.run, fn), *args, **kwargs)
