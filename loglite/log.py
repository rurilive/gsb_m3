"""结构化日志层：级别过滤、线程本地上下文、大小轮转文件 sink。

默认配置是一条兼容模式的 stdout sink：渲染不带级别与上下文装饰，
模块从裸 print 切到日志层后 stdout 输出逐字节不变。
"""

import os
import sys
import threading

DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40

LEVEL_NAMES = {DEBUG: "DEBUG", INFO: "INFO", WARNING: "WARNING", ERROR: "ERROR"}

_state = threading.local()
_emit_lock = threading.Lock()
_sinks = []
_level = INFO


def set_level(level):
    """设置全局级别，低于级别的消息不进任何 sink。"""
    global _level
    _level = level


def get_level():
    return _level


def set_context(**fields):
    """写入当前线程的上下文字段（多次调用累积），之后每条日志自动附上。"""
    ctx = getattr(_state, "context", None)
    merged = dict(ctx) if ctx else {}
    merged.update(fields)
    _state.context = merged


def clear_context():
    """清除当前线程的全部上下文字段。"""
    _state.context = None


def get_context():
    ctx = getattr(_state, "context", None)
    return dict(ctx) if ctx else {}


def render(level, message, context, compat=False):
    """把一条记录渲染成单行文本；compat 模式与旧 print 输出一致。"""
    if compat:
        return message
    line = f"{LEVEL_NAMES[level]} {message}"
    if context:
        line += " " + " ".join(f"{key}={value}" for key, value in context.items())
    return line


class StreamSink:
    """写文本流的 sink；stream 为 None 时每次取当前 sys.stdout。"""

    def __init__(self, stream=None, compat=False):
        self.stream = stream
        self.compat = compat

    def emit(self, line):
        stream = self.stream if self.stream is not None else sys.stdout
        stream.write(line + "\n")
        stream.flush()


class RotatingFileSink:
    """按大小轮转的文本文件 sink。

    当前文件再写一行会超过 max_bytes 时先轮转：
    path -> path.1 -> ... -> path.backups，更旧的文件删除。
    """

    def __init__(self, path, max_bytes, backups, compat=False):
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        if backups < 1:
            raise ValueError("backups must be >= 1")
        self.path = path
        self.max_bytes = max_bytes
        self.backups = backups
        self.compat = compat

    def emit(self, line):
        data = (line + "\n").encode("utf-8")
        if (
            os.path.exists(self.path)
            and os.path.getsize(self.path) + len(data) > self.max_bytes
        ):
            self._rotate()
        with open(self.path, "ab") as f:
            f.write(data)

    def _rotate(self):
        oldest = f"{self.path}.{self.backups}"
        if os.path.exists(oldest):
            os.remove(oldest)
        for idx in range(self.backups - 1, 0, -1):
            src = f"{self.path}.{idx}"
            if os.path.exists(src):
                os.replace(src, f"{self.path}.{idx + 1}")
        if os.path.exists(self.path):
            os.replace(self.path, f"{self.path}.1")


class Logger:
    def __init__(self, name):
        self.name = name

    def log(self, level, message):
        if level < _level:
            return
        context = get_context()
        with _emit_lock:
            for sink in list(_sinks):
                sink.emit(render(level, message, context, compat=sink.compat))

    def debug(self, message):
        self.log(DEBUG, message)

    def info(self, message):
        self.log(INFO, message)

    def warning(self, message):
        self.log(WARNING, message)

    def error(self, message):
        self.log(ERROR, message)


_loggers = {}


def get_logger(name):
    if name not in _loggers:
        _loggers[name] = Logger(name)
    return _loggers[name]


def add_sink(sink):
    _sinks.append(sink)


def remove_sink(sink):
    _sinks.remove(sink)


def clear_sinks():
    del _sinks[:]


def reset():
    """恢复默认配置：INFO 级别、清空本线程上下文、仅一条兼容 stdout sink。"""
    global _level
    _level = INFO
    clear_context()
    clear_sinks()
    _sinks.append(StreamSink(compat=True))


reset()
