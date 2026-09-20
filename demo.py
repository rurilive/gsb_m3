"""巡检工具包演示。

第一段：跑一遍 扫描 -> 核查 -> 处置 流水线。
第二段：结构化日志层（兼容输出、级别过滤、上下文字段、文件轮转）。
"""

import io
import os
import tempfile

from loglite import log
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


def demo_logging():
    print("\n=== 结构化日志层 ===\n")

    print("-- 兼容模式：模块输出与旧 print 逐字节一致 --")
    scan(parse("x.tmp 1 1000\n"))

    print("\n-- 级别过滤：WARNING 以下不进 sink --")
    buf = io.StringIO()
    log.clear_sinks()
    log.add_sink(log.StreamSink(buf))
    log.set_level(log.WARNING)
    scan(parse("y.bak 1 1000\n"))
    print(f"sink 收到 {len(buf.getvalue().splitlines())} 行（scanner 的 INFO 全部被过滤）")

    print("\n-- 上下文字段：set_context 后每条日志自动附上 --")
    log.set_level(log.INFO)
    log.set_context(run="demo-1", stage="scan")
    scan(parse("z.swp 1 1000\n"))
    log.clear_context()
    print("sink 捕获（带级别与上下文）:")
    for line in buf.getvalue().splitlines():
        print(f"  {line}")

    print("\n-- 文件 sink 按大小轮转 --")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "pipeline.log")
        log.clear_sinks()
        log.add_sink(log.RotatingFileSink(path, max_bytes=120, backups=2))
        for i in range(6):
            log.get_logger("demo").info(f"record-{i:04d} payload")
        for name in sorted(os.listdir(d)):
            size = os.path.getsize(os.path.join(d, name))
            print(f"  {name} ({size} bytes)")

    log.reset()


if __name__ == "__main__":
    main()
    print()
    demo_logging()
