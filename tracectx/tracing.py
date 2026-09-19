"""跨线程调用链上下文：correlation-id、span 计时与树形报告。

纯标准库实现，基于 contextvars：上下文在包装线程/线程池提交任务时
快照迁移，链路并发之间互不串号；span 通过父子指针组织成树，子 span
即便在工作线程里创建，也会挂到提交方的当前 span 下。
"""

import contextvars
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

DEFAULT_SLOW_THRESHOLD = 0.1

_current_cid = contextvars.ContextVar("tracectx_cid", default=None)
_current_span = contextvars.ContextVar("tracectx_span", default=None)


def new_cid():
    """生成一个 correlation-id（cid- 前缀 + 12 位 uuid hex）。"""
    return "cid-" + uuid.uuid4().hex[:12]


def current_cid():
    """返回当前线程当前上下文里的 correlation-id，没有则 None。"""
    return _current_cid.get()


def current_span():
    """返回当前上下文里的 span，没有则 None。"""
    return _current_span.get()


class Span:
    """一段带名字的计时区间，支持嵌套与跨线程挂接。

    一般通过 span() / trace_session() 创建，不要直接 new。
    """

    __slots__ = ("name", "cid", "parent", "level", "slow_threshold",
                 "start", "end", "children", "_lock")

    def __init__(self, name, cid, parent, slow_threshold):
        self.name = name
        self.cid = cid
        self.parent = parent
        self.level = 0 if parent is None else parent.level + 1
        self.slow_threshold = slow_threshold
        self.start = time.monotonic()
        self.end = None
        self.children = []
        self._lock = threading.Lock()
        if parent is not None:
            with parent._lock:
                parent.children.append(self)

    def close(self):
        """结束计时；重复调用安全，以第一次结束为准。"""
        if self.end is None:
            self.end = time.monotonic()

    @property
    def elapsed(self):
        """span 耗时（秒），未结束时返回截至当前的时长。"""
        return (self.end if self.end is not None else time.monotonic()) - self.start

    @property
    def slow(self):
        """耗时严格超过阈值即为慢 span；阈值 None 表示永不判定。"""
        if self.slow_threshold is None:
            return False
        return self.elapsed > self.slow_threshold

    def snapshot_children(self):
        with self._lock:
            return list(self.children)

    def to_tree(self):
        """把本 span 及其后代渲染成按层级缩进的多行文本。"""
        return format_tree(self)


def span(name, slow_threshold=None):
    """创建一个子 span 并挂到当前 span 下（无则成为游离根 span）。

    作为上下文管理器使用；slow_threshold 缺省继承父 span/会话设置，
    没有可继承的值时取 DEFAULT_SLOW_THRESHOLD。
    """
    return _SpanContext(name, slow_threshold)


class _SpanContext:
    def __init__(self, name, slow_threshold):
        self._name = name
        self._threshold_arg = slow_threshold
        self._span = None
        self._token_cid = None
        self._token_span = None

    def __enter__(self):
        parent = _current_span.get()
        cid = _current_cid.get()
        if self._threshold_arg is not None:
            threshold = self._threshold_arg
        elif parent is not None:
            threshold = parent.slow_threshold
        else:
            threshold = DEFAULT_SLOW_THRESHOLD
        s = Span(self._name, cid, parent, threshold)
        self._span = s
        if cid is None:
            self._token_cid = _current_cid.set(new_cid())
        self._token_span = _current_span.set(s)
        return s

    def __exit__(self, exc_type, exc, tb):
        self._span.close()
        _current_span.reset(self._token_span)
        if self._token_cid is not None:
            _current_cid.reset(self._token_cid)


def trace_session(name="trace", cid=None, slow_threshold=DEFAULT_SLOW_THRESHOLD):
    """开启一条调用链：生成（或使用给定的）correlation-id，建根 span。

    as 出来的对象上 .cid 是链路 id，.root 是根 span；退出上下文时
    结束根 span，之后可用 root.to_tree() 打印整棵树。
    """
    return _SessionContext(name, cid if cid is not None else new_cid(),
                           slow_threshold)


class _SessionContext:
    def __init__(self, name, cid, slow_threshold):
        self.name = name
        self.cid = cid
        self.slow_threshold = slow_threshold
        self.root = None
        self._token_cid = None
        self._token_span = None

    def __enter__(self):
        self.root = Span(self.name, self.cid, None, self.slow_threshold)
        self._token_cid = _current_cid.set(self.cid)
        self._token_span = _current_span.set(self.root)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.root.close()
        _current_span.reset(self._token_span)
        _current_cid.reset(self._token_cid)


def _format_elapsed(seconds):
    if seconds < 1:
        return "%.3fms" % (seconds * 1000.0)
    return "%.3fs" % seconds


def format_tree(root):
    """按嵌套层级缩进渲染 span 树。

    每行形如 ``  name  耗时  [slow]``：2 空格一级缩进，慢 span
    追加 [slow] 标记。
    """
    lines = []

    def walk(s):
        line = "  " * s.level + "%s  %s" % (s.name, _format_elapsed(s.elapsed))
        if s.slow:
            line += "  [slow]"
        lines.append(line)
        for child in s.snapshot_children():
            walk(child)

    walk(root)
    return "\n".join(lines)


class TracedThread(threading.Thread):
    """threading.Thread 子类：start 时快照当前链路上下文。

    包出来的线程在同一 correlation-id 与当前 span 下执行；多条并发
    线程各自持有独立快照，互不串号。构造参数与 threading.Thread 一致。
    """

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None,
                 *, daemon=None):
        self._user_target = target
        self._user_args = args
        self._user_kwargs = kwargs or {}
        self._trace_ctx = None
        super().__init__(group=group, target=None, name=name, daemon=daemon)

    def start(self):
        if self._trace_ctx is None:
            self._trace_ctx = contextvars.copy_context()
        super().start()

    def run(self):
        ctx = self._trace_ctx
        if ctx is None:  # 未走 start 直接调用 run
            ctx = contextvars.copy_context()
        ctx.run(self._user_entry)

    def _user_entry(self):
        if self._user_target is not None:
            self._user_target(*self._user_args, **self._user_kwargs)


class TracedThreadPoolExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor 子类：submit 时快照当前链路上下文。

    通过 submit（以及 map/with 等内部走 submit 的入口）提交的任务，
    都在提交方当前 correlation-id 与当前 span 的快照里执行。
    """

    def submit(self, fn, /, *args, **kwargs):
        ctx = contextvars.copy_context()
        return super().submit(ctx.run, _call_with, fn, args, kwargs)


def _call_with(fn, args, kwargs):
    return fn(*args, **kwargs)
