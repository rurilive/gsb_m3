"""结构化日志层。

- 级别过滤：DEBUG/INFO/WARNING/ERROR，全局级别（set_level），
  低于当前级别的记录不进入任何 sink。
- 上下文字段：threading.local 保存，set_context 后当前线程发出的
  每条记录自动附上，线程间互不串，clear_context 清除。
- Sink：StreamSink（默认接 sys.stdout，兼容模式渲染）、CaptureSink
  （测试捕获）、FileSink（按大小轮转，最多保留 backups 个旧文件）。
- 兼容模式：plain 渲染只输出 ``前缀 + 消息``，与旧裸 print 逐字一致，
  不带级别与上下文装饰。
"""

import json
import os
import sys
import threading
import time
from datetime import datetime

DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40

LEVELS = {
    "DEBUG": DEBUG,
    "INFO": INFO,
    "WARNING": WARNING,
    "ERROR": ERROR,
}

NAMES = {value: name for name, value in LEVELS.items()}


def _level_value(level):
    if isinstance(level, str):
        try:
            return LEVELS[level.upper()]
        except KeyError:
            raise ValueError(f"bad log level: {level!r}")
    if level not in NAMES:
        raise ValueError(f"bad log level: {level!r}")
    return level


class Record:
    """一条日志记录。"""

    def __init__(self, level, name, message, context, created=None):
        self.level = level
        self.levelname = NAMES[level]
        self.name = name
        self.message = message
        self.context = dict(context)
        self.created = time.time() if created is None else created

    @property
    def asctime(self):
        return datetime.fromtimestamp(self.created).isoformat(timespec="milliseconds")


def render_plain(record):
    """兼容模式渲染：只有前缀与消息，不含级别、时间、上下文。"""
    return record.message


def render_text(record):
    """人类可读的结构化文本：时间 级别 logger 消息 [k=v ...]。"""
    parts = [record.asctime, record.levelname, record.name, record.message]
    if record.context:
        fields = " ".join(f"{key}={value}" for key, value in record.context.items())
        parts.append(f"[{fields}]")
    return " ".join(parts)


def render_json(record):
    """JSON 结构化渲染。"""
    data = {
        "ts": record.asctime,
        "level": record.levelname,
        "logger": record.name,
        "msg": record.message,
    }
    data.update(record.context)
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


RENDERERS = {
    "plain": render_plain,
    "text": render_text,
    "json": render_json,
}


def _as_renderer(render):
    if render is None:
        return render_plain
    if callable(render):
        return render
    try:
        return RENDERERS[render]
    except KeyError:
        raise ValueError(f"unknown renderer: {render!r}")


class Sink:
    """sink 基类，子类实现 write。"""

    def write(self, record, line):
        raise NotImplementedError

    def close(self):
        pass


class StreamSink(Sink):
    """把渲染结果写进文本流；stream=None 时每次取当前 sys.stdout。

    动态读取 sys.stdout 才能与裸 print 一样被 redirect_stdout 捕获，
    默认不 flush，行为也与 print 一致。
    """

    def __init__(self, stream=None, render="plain"):
        self.stream = stream
        self.render = _as_renderer(render)

    def write(self, record, line):
        stream = sys.stdout if self.stream is None else self.stream
        stream.write(line + "\n")


class CaptureSink(Sink):
    """把 Record 与渲染后的行收集到内存，供测试断言。"""

    def __init__(self, render="text"):
        self.render = _as_renderer(render)
        self.records = []
        self.lines = []

    def write(self, record, line):
        self.records.append(record)
        self.lines.append(line)


class FileSink(Sink):
    """文件 sink，按写入大小轮转。

    当前文件超过 max_bytes 时，path 依次轮转为 path.1、path.2……
    最多保留 backups 个旧文件（path.1 最新），更旧的删除。
    大小在写入前判断，保证单条记录不被切到两个文件。
    """

    def __init__(self, path, max_bytes, backups=5, render="text", encoding="utf-8"):
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.path = path
        self.max_bytes = max_bytes
        self.backups = backups
        self.render = _as_renderer(render)
        self.encoding = encoding
        self._lock = threading.RLock()
        self._file = open(path, "a", encoding=encoding)
        self._pos = self._file.tell()

    def write(self, record, line):
        data = (line + "\n").encode(self.encoding)
        with self._lock:
            if self._pos > 0 and self._pos + len(data) > self.max_bytes:
                self._rotate()
            self._file.write(line + "\n")
            self._file.flush()
            self._pos += len(data)

    def _rotate(self):
        self._file.close()
        if self.backups > 0:
            oldest = f"{self.path}.{self.backups}"
            if os.path.exists(oldest):
                os.remove(oldest)
            for idx in range(self.backups, 1, -1):
                source = f"{self.path}.{idx - 1}"
                if os.path.exists(source):
                    os.replace(source, f"{self.path}.{idx}")
            os.replace(self.path, f"{self.path}.1")
        self._file = open(self.path, "w", encoding=self.encoding)
        self._pos = 0

    def close(self):
        with self._lock:
            if not self._file.closed:
                self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


_lock = threading.RLock()
_level = INFO
_sinks = [StreamSink()]
_loggers = {}

_context = threading.local()


def _context_stack():
    stack = getattr(_context, "stack", None)
    if stack is None:
        stack = []
        _context.stack = stack
    return stack


def set_context(**fields):
    """在当前线程的上下文里写入字段（同名覆盖），返回当前快照。"""
    stack = _context_stack()
    if not stack:
        stack.append({})
    base = stack.pop()
    base.update(fields)
    stack.append(base)
    return dict(base)


def push_context(**fields):
    """压入一层上下文副本，与 pop_context 配对做作用域隔离。"""
    stack = _context_stack()
    base = dict(stack[-1]) if stack else {}
    base.update(fields)
    stack.append(base)
    return dict(base)


def pop_context():
    """弹出 push_context 压入的上下文层，返回弹出后的快照。"""
    stack = _context_stack()
    if stack:
        stack.pop()
    return get_context()


def get_context():
    """当前线程的上下文快照（拷贝）。"""
    stack = _context_stack()
    return dict(stack[-1]) if stack else {}


def clear_context():
    """清除当前线程的全部上下文字段。"""
    _context.stack = []


def set_level(level):
    """设置全局级别，可为名称（"INFO"）或整数（INFO）。"""
    global _level
    value = _level_value(level)
    with _lock:
        _level = value


def get_level():
    """当前全局级别。"""
    with _lock:
        return _level


def add_sink(*new_sinks):
    """追加 sink，返回已注册的 sink 列表拷贝。"""
    with _lock:
        _sinks.extend(new_sinks)
        return list(_sinks)


def remove_sink(sink):
    """移除一个 sink。"""
    with _lock:
        try:
            _sinks.remove(sink)
        except ValueError:
            pass


def clear_sinks():
    """移除全部 sink。"""
    with _lock:
        _sinks.clear()


def reset():
    """恢复默认配置：INFO 级别、单一 stdout 兼容 sink、清空当前线程上下文。

    主要供测试做用例间隔离。
    """
    global _sinks, _level
    with _lock:
        _sinks.clear()
        _sinks.append(StreamSink())
        _level = INFO
    clear_context()


class Logger:
    """带名字与兼容前缀的日志器。"""

    def __init__(self, name, prefix=None):
        self.name = name
        self.prefix = f"[{name}] " if prefix is None else prefix

    def _log(self, level, message):
        with _lock:
            if level < _level:
                return
            sinks = list(_sinks)
            context = get_context()
        record = Record(level, self.name, f"{self.prefix}{message}", context)
        for sink in sinks:
            sink.write(record, sink.render(record))

    def debug(self, message):
        self._log(DEBUG, message)

    def info(self, message):
        self._log(INFO, message)

    def warning(self, message):
        self._log(WARNING, message)

    def error(self, message):
        self._log(ERROR, message)

    def log(self, level, message):
        """按显式级别记录，level 可为名称或整数。"""
        self._log(_level_value(level), message)


def get_logger(name, prefix=None):
    """按名字取日志器；同名复用同一实例，首次给定的前缀生效。"""
    with _lock:
        logger = _loggers.get(name)
        if logger is None:
            logger = Logger(name, prefix)
            _loggers[name] = logger
        return logger
