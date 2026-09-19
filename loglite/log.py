"""结构化日志层：级别过滤、线程上下文字段、按大小轮转的文件 sink。

默认处于兼容模式：渲染不带级别与上下文装饰，stdout 与旧 print 完全一致；
set_compat(False) 后按 `LEVEL name key=value msg` 渲染。
"""

import os
import sys
import threading

DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40

_LEVEL_NAMES = {DEBUG: "DEBUG", INFO: "INFO", WARNING: "WARNING", ERROR: "ERROR"}
_NAME_LEVELS = {name: level for level, name in _LEVEL_NAMES.items()}

_level = INFO
_compat = True
_sinks = []
_sinks_lock = threading.Lock()
_local = threading.local()


def set_level(level):
    """设置全局级别（DEBUG/INFO/WARNING/ERROR 常量或名字），低于级别的消息不进 sink。"""
    global _level
    if isinstance(level, str):
        level = _NAME_LEVELS[level.upper()]
    _level = level


def get_level():
    return _level


def set_compat(on=True):
    """切换兼容模式：True 时只渲染消息本体，与旧 print 输出一致。"""
    global _compat
    _compat = bool(on)


def set_context(fields=None, **kw):
    """写入本线程的上下文字段，之后每条日志自动附上；线程间互不影响。"""
    ctx = getattr(_local, "ctx", None)
    if ctx is None:
        ctx = _local.ctx = {}
    if fields:
        ctx.update(fields)
    ctx.update(kw)


def clear_context():
    """清除本线程的全部上下文字段。"""
    _local.ctx = {}


def add_sink(sink):
    """追加一个 sink（任何带 emit(text) 方法的对象）。"""
    with _sinks_lock:
        _sinks.append(sink)


def clear_sinks():
    with _sinks_lock:
        del _sinks[:]


def reset():
    """恢复默认：INFO 级别、兼容模式、唯一 stdout sink，并清除本线程上下文。"""
    global _level, _compat
    _level = INFO
    _compat = True
    clear_sinks()
    add_sink(StreamSink())
    clear_context()


def _render(level, name, msg):
    if _compat:
        return msg
    parts = [_LEVEL_NAMES[level], name]
    ctx = getattr(_local, "ctx", None)
    if ctx:
        parts.append(" ".join(f"{key}={value}" for key, value in ctx.items()))
    parts.append(msg)
    return " ".join(parts)


class Logger:
    """按名字获取的日志器，消息先过全局级别过滤再渲染分发。"""

    def __init__(self, name):
        self.name = name

    def log(self, level, msg):
        if level < _level:
            return
        text = _render(level, self.name, msg)
        with _sinks_lock:
            sinks = list(_sinks)
        for sink in sinks:
            sink.emit(text)

    def debug(self, msg):
        self.log(DEBUG, msg)

    def info(self, msg):
        self.log(INFO, msg)

    def warning(self, msg):
        self.log(WARNING, msg)

    def error(self, msg):
        self.log(ERROR, msg)


def get_logger(name):
    return Logger(name)


class StreamSink:
    """写文本行的流 sink；stream 缺省时在写入时取当前 sys.stdout。"""

    def __init__(self, stream=None):
        self._stream = stream

    def emit(self, text):
        stream = self._stream if self._stream is not None else sys.stdout
        stream.write(text + "\n")


class RotatingFileSink:
    """按大小轮转的文件 sink：写入会超过 max_bytes 时先轮转，
    path -> path.1 -> path.2 依次后移，最多留 backups 个旧文件，更旧删掉。"""

    def __init__(self, path, max_bytes, backups):
        self.path = path
        self.max_bytes = max_bytes
        self.backups = backups
        self._lock = threading.Lock()

    def emit(self, text):
        data = (text + "\n").encode("utf-8")
        with self._lock:
            if self._need_rotation(len(data)):
                self._rotate()
            with open(self.path, "ab") as f:
                f.write(data)

    def _need_rotation(self, incoming):
        if self.max_bytes <= 0:
            return False
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return False
        return size > 0 and size + incoming > self.max_bytes

    def _rotate(self):
        if self.backups <= 0:
            if os.path.exists(self.path):
                os.remove(self.path)
            return
        oldest = f"{self.path}.{self.backups}"
        if os.path.exists(oldest):
            os.remove(oldest)
        for i in range(self.backups - 1, 0, -1):
            src = f"{self.path}.{i}"
            if os.path.exists(src):
                os.replace(src, f"{self.path}.{i + 1}")
        if os.path.exists(self.path):
            os.replace(self.path, f"{self.path}.1")


reset()
