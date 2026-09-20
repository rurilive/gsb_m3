"""核查阶段：重复条目与异常 mtime。

过程日志走 loglite.log，兼容模式下前缀仍是 `==> checker:`。
"""

import time

from .log import get_logger

FUTURE_MARGIN = 60  # mtime 超出当前时间 60s 视为异常

_log = get_logger("checker", compat_prefix="==> checker:")


def check(entries, now=None):
    """返回问题列表 [(name, code)]，code 为 DUPLICATE / FUTURE_MTIME。

    now 可注入，便于测试固定时间基准。
    """
    if now is None:
        now = time.time()
    _log.info(f"begin over {len(entries)} entries")
    problems = []
    seen = set()
    for name, _size, _mtime in entries:
        if name in seen:
            problems.append((name, "DUPLICATE"))
            _log.warning(f"duplicate entry {name}")
        seen.add(name)
    for name, _size, mtime in entries:
        if mtime > now + FUTURE_MARGIN:
            problems.append((name, "FUTURE_MTIME"))
            _log.warning(f"mtime in future: {name}")
    _log.info(f"found {len(problems)} problem(s)")
    return problems
