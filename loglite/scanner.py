"""扫描阶段：从清单条目里筛出可疑项。

过程日志走 loglite.log，兼容模式下前缀仍是 `[scanner]`。
"""

from .log import get_logger

MAX_ENTRY_SIZE = 1024 * 1024
TEMP_SUFFIXES = (".tmp", ".bak", ".swp")

_log = get_logger("scanner", compat_prefix="[scanner]")


def scan(entries):
    """返回可疑条目名列表：临时后缀或超出大小上限。"""
    _log.info(f"start: {len(entries)} entries")
    flagged = []
    for name, size, _mtime in entries:
        if name.endswith(TEMP_SUFFIXES):
            flagged.append(name)
            _log.info(f"flagged {name} (temp suffix)")
        elif size > MAX_ENTRY_SIZE:
            flagged.append(name)
            _log.info(f"flagged {name} (size {size} over limit)")
    ok = len(entries) - len(flagged)
    _log.info(f"done: {ok} ok, {len(flagged)} flagged")
    return flagged
