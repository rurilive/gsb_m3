"""结构化日志层：级别过滤、线程上下文、可轮转文件 sink。

默认兼容模式：渲染结果与旧裸 print 完全一致（仅消息文本，可带
模块前缀），模块接入后 stdout 不变；set_structured(True) 后输出
带级别、logger 名与上下文字段，供统一采集解析。
"""

import os
import sys
import threading

LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}

_lock = threading.RLock()
_local = threading.local()
_level = LEVELS["INFO"]
_structured = False


def set_level(level):
    """设置全局级别（DEBUG/INFO/WARNING/ERROR），低于级别的消息不进 sink。"""
    global _level
    if isinstance(level, str):
        level = level.upper()
        if level not in LEVELS:
            raise ValueError(f"unknown log level: {level!r}")
        _level = LEVELS[level]
    else:
        _level = int(level)


def set_structured(enabled=True):
    """切换渲染模式：True 带级别/上下文装饰，False 与旧 print 一致。"""
    global _structured
    _structured = bool(enabled)


def set_context(**fields):
    """设置当前线程的上下文字段，之后每条日志自动附上（线程间隔离）。"""
    ctx = getattr(_local, "ctx", None)
    if ctx is None:
        ctx = _local.ctx = {}
    ctx.update(fields)


def clear_context():
    """清空当前线程的上下文字段。"""
    _local.ctx = {}


class StreamSink:
    """写文本流的 sink；stream 为 None 时动态取 sys.stdout。"""

    def __init__(self, stream=None):
        self.stream = stream

    def emit(self, line):
        stream = self.stream if self.stream is not None else sys.stdout
        stream.write(line + "\n")
        stream.flush()


class RotatingFileSink:
    """按大小轮转的文本文件 sink。

    当前文件写入后将超过 max_bytes 时先轮转：path 改名 path.1，
    旧的 path.N 后移为 path.N+1，最多保留 backups 个旧文件，
    更旧的删除。
    """

    def __init__(self, path, max_bytes, backups):
        self.path = str(path)
        self.max_bytes = int(max_bytes)
        self.backups = int(backups)

    def emit(self, line):
        data = (line + "\n").encode("utf-8")
        with _lock:
            if (
                self.max_bytes > 0
                and os.path.exists(self.path)
                and os.path.getsize(self.path) + len(data) > self.max_bytes
            ):
                self._rotate()
            with open(self.path, "ab") as f:
                f.write(data)

    def _rotate(self):
        if self.backups <= 0:
            os.remove(self.path)
            return
        stale = f"{self.path}.{self.backups}"
        if os.path.exists(stale):
            os.remove(stale)
        for idx in range(self.backups - 1, 0, -1):
            src = f"{self.path}.{idx}"
            if os.path.exists(src):
                os.replace(src, f"{self.path}.{idx + 1}")
        os.replace(self.path, f"{self.path}.1")


_sinks = [StreamSink()]


def add_sink(sink):
    """追加一个 sink（在默认 stdout sink 之上）。"""
    with _lock:
        _sinks.append(sink)


def remove_sink(sink):
    """移除一个已注册的 sink。"""
    with _lock:
        _sinks.remove(sink)


def reset_sinks():
    """恢复默认：仅 stdout sink。"""
    with _lock:
        del _sinks[:]
        _sinks.append(StreamSink())


class Logger:
    """具名 logger；compat_prefix 用于兼容模式还原旧 print 前缀。"""

    def __init__(self, name, compat_prefix=None):
        self.name = name
        self.compat_prefix = compat_prefix

    def log(self, level, msg):
        if LEVELS[level] < _level:
            return
        if _structured:
            line = f"{level} [{self.name}] {msg}"
            ctx = getattr(_local, "ctx", None)
            if ctx:
                line += " " + " ".join(f"{key}={value}" for key, value in ctx.items())
        elif self.compat_prefix:
            line = f"{self.compat_prefix} {msg}"
        else:
            line = msg
        with _lock:
            for sink in list(_sinks):
                sink.emit(line)

    def debug(self, msg):
        self.log("DEBUG", msg)

    def info(self, msg):
        self.log("INFO", msg)

    def warning(self, msg):
        self.log("WARNING", msg)

    def error(self, msg):
        self.log("ERROR", msg)


def get_logger(name, compat_prefix=None):
    """获取具名 logger；compat_prefix 为兼容模式下拼在消息前的前缀。"""
    return Logger(name, compat_prefix)
