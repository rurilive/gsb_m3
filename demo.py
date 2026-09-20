"""巡检工具包演示。

第一段：跑一遍 扫描 -> 核查 -> 处置 流水线。
第二段：结构化日志层（兼容模式 / 结构化模式 / 级别过滤 / 文件轮转）。
"""

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
    print("\n=== 结构化日志层 ===")

    # 第一段即兼容模式：三模块输出与旧 print 逐字一致，这里不再重复。

    # 结构化模式：带级别、logger 名与线程上下文字段
    log.set_structured(True)
    log.set_context(stage="scan", run="demo")
    print("-- 结构化模式 + 上下文字段 --")
    scan(parse(MANIFEST))
    log.clear_context()

    # 级别过滤：WARNING 下 INFO 不进 sink
    log.set_level("WARNING")
    print("-- 级别 WARNING：scan 的 INFO 被过滤（无日志行） --")
    scan(parse(MANIFEST))
    log.set_level("INFO")

    # 文件 sink 按大小轮转
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "loglite.log")
        log.add_sink(log.RotatingFileSink(path, max_bytes=200, backups=2))
        print("-- 文件轮转（max_bytes=200, backups=2），stdout 与文件双写 --")
        for _ in range(3):
            scan(parse(MANIFEST))
        log.reset_sinks()
        print(f"轮转产物: {sorted(os.listdir(d))}")

    log.set_structured(False)
    print("（已恢复兼容模式与默认 stdout sink）")


if __name__ == "__main__":
    main()
    demo_logging()
