"""巡检工具包现状演示。

第一段：跑一遍 扫描 -> 核查 -> 处置 流水线。
第二段：结构化日志层演示（级别过滤 / 上下文字段 / 文件轮转）。
"""

import os
import tempfile

from loglite.checker import check
from loglite.logging import (
    FileSink,
    StreamSink,
    add_sink,
    clear_sinks,
    get_logger,
    reset,
    set_context,
    set_level,
)
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

    demo_structured_logging()


def demo_structured_logging():
    """第二段：级别过滤、上下文字段、文件轮转。"""
    print("\n=== 结构化日志演示 ===")
    tmpdir = tempfile.mkdtemp(prefix="loglite-demo-")
    path = os.path.join(tmpdir, "inspect.jsonl")
    print(f"日志文件目录: {tmpdir}")

    reset()  # 与第一段隔离：恢复默认级别与 sink
    # 控制台换成带级别/上下文的 text 渲染，文件用 JSON 并按大小轮转
    clear_sinks()
    add_sink(
        StreamSink(render="text"),
        FileSink(path, max_bytes=400, backups=2, render="json"),
    )
    set_level("DEBUG")
    set_context(run="nightly", host="repo-1")
    log = get_logger("demo")

    log.debug("级别已放开到 DEBUG：这行能进 sink")
    log.info("开始演示结构化采集")
    set_context(stage="inspect")  # 后续记录自动多带一个字段
    log.warning("发现 1 个待人工复核项")

    set_level("WARNING")
    log.info("级别收回 WARNING：这行不会出现")
    log.error("演示一条 ERROR")

    # 多写几条触发按大小轮转：path.1 / path.2 依次后移
    for idx in range(12):
        log.warning(f"轮转填充消息 {idx}")

    rotated = sorted(name for name in os.listdir(tmpdir) if name.startswith("inspect"))
    print(f"轮转后文件: {rotated}")
    for name in rotated:
        print(f"  {name}: {os.path.getsize(os.path.join(tmpdir, name))} 字节")
    with open(path, "r", encoding="utf-8") as f:
        print(f"当前文件末行示例: {f.readline().rstrip()}")

    reset()  # 恢复默认配置，不影响后续在同进程里的使用


if __name__ == "__main__":
    main()
