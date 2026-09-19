"""巡检工具包演示。

第一段：跑一遍 扫描 -> 核查 -> 处置 流水线（兼容模式，输出与旧 print 一致）。
第二段：结构化日志层演示——级别过滤、上下文字段、文件轮转。
"""

import os
import shutil
import tempfile

from loglite import log as logmod
from loglite.checker import check
from loglite.manifest import dump, parse
from loglite.planner import plan, summary
from loglite.scanner import scan

MANIFEST = """\
# name size mtime
site.conf      2048      1758000000
notes.txt      512       1758000100
cache.tmp      65536     1758000200
site.conf      2048      1758000300
huge.blob      9437184   1758000400
editor.swp     4096      1758000500
"""


def main():
    entries = parse(MANIFEST)
    print(f"=== 巡检流水线（{len(entries)} 个条目） ===\n")

    flagged = scan(entries)
    print()
    problems = check(entries)
    print()
    actions = plan(problems)

    print("\n=== 结果 ===")
    print(f"  可疑条目: {flagged}")
    print(f"  问题清单: {problems}")
    print(f"  处置动作: {actions}")
    print(f"  动作汇总: {summary(actions)}")
    kept = [e for e in entries if e[0] not in flagged]
    print(f"\n清理后的清单预览:\n{dump(kept)}", end="")

    # ---- 第二段：结构化日志层 ----
    print("\n=== 结构化日志层 ===")

    print("\n-- 级别过滤：全局 WARNING，scan 的 INFO 过程日志全部静默 --")
    logmod.set_level(logmod.WARNING)
    scan(entries)
    print("（上面没有任何 scan 输出）")
    logmod.set_level(logmod.INFO)

    print("\n-- 结构化渲染 + 线程上下文字段 --")
    logmod.set_compat(False)
    logmod.set_context(run="demo-1", stage="scan")
    scan(entries[:2])
    logmod.clear_context()
    logmod.set_compat(True)

    print("\n-- 文件 sink 按大小轮转（max_bytes=64, backups=2） --")
    tmpdir = tempfile.mkdtemp()
    try:
        path = os.path.join(tmpdir, "audit.log")
        logmod.clear_sinks()
        logmod.add_sink(logmod.RotatingFileSink(path, max_bytes=64, backups=2))
        logger = logmod.get_logger("demo")
        for i in range(12):
            logger.info(f"audit line {i}")
        for name in sorted(os.listdir(tmpdir)):
            with open(os.path.join(tmpdir, name), encoding="utf-8") as f:
                print(f"  {name}: {f.read().splitlines()}")
    finally:
        logmod.reset()
        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    main()
