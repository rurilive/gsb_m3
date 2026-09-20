"""路径匹配现状演示。

第一段：段级 glob 的行为（* 不跨段、段数对齐）。
第二段：把源码树里的一批路径按几种 pattern 逐条过一遍。
"""

from pathmatch.match import match
from pathmatch.ignore import IgnoreRules, matched

PATTERNS = ["*.py", "src/*.py", "src/*/*.py", "assets/*", "docs/*.md"]
TREE = [
    "main.py",
    "src/main.py",
    "src/core/engine.py",
    "src/util/log.py",
    "assets/logo.svg",
    "docs/notes.md",
    "build.log",
]

ROOT_IGNORE = """\
# 生成物
*.o
*.log
build/
!keep.log
docs/**
!docs/spec.md
"""

SRC_IGNORE = """\
# src 目录自己的规则：重新放开调试日志
!debug.log
*.tmp
"""

IGNORE_FILES = {
    "": ROOT_IGNORE,
    "src": SRC_IGNORE,
}

IGNORE_TREE = [
    ("main.py", False),
    ("build", True),
    ("build/app.o", False),
    ("src", True),
    ("src/app.o", False),
    ("src/debug.log", False),
    ("src/scratch.tmp", False),
    ("docs", True),
    ("docs/spec.md", False),
    ("docs/draft.md", False),
    ("keep.log", False),
    ("error.log", False),
]


def main():
    print("=== 段级 glob：* 不跨段，段数必须对齐 ===")
    for pat in PATTERNS:
        hits = [p for p in TREE if match(pat, p)]
        print(f"  {pat:<12} 命中 {len(hits)} 条")
        for h in hits:
            print(f"      {h}")

    print("\n=== 逐条判定（pattern=src/*.py） ===")
    for p in TREE:
        print(f"  {str(match('src/*.py', p)):<5} {p}")

    print("\n=== .gitignore 语义：否定 / 目录限定 / 跨段 ** / 嵌套优先 ===")
    compiled = {base: IgnoreRules(text, base) for base, text in IGNORE_FILES.items()}
    pruned = []
    for path, is_dir in IGNORE_TREE:
        if any(path == d or path.startswith(d + "/") for d in pruned):
            continue
        parts = path.split("/")
        prefixes = [""] + ["/".join(parts[:i]) for i in range(1, len(parts))]
        stack = [compiled[pre] for pre in prefixes if pre in compiled]
        status, rule = matched(path, is_dir, stack)
        decided = f"{rule.text}  (@{rule.base or '.'}:{rule.lineno})" if rule else "-"
        suffix = "/" if is_dir else ""
        print(f"  {status:<7} {path + suffix:<22} <- {decided}")
        if is_dir and status == "ignored":
            pruned.append(path)
    skipped = [p for p, _ in IGNORE_TREE if any(p.startswith(d + "/") for d in pruned)]
    for p in skipped:
        print(f"  pruned  {p:<22} <- 父目录已被忽略")


if __name__ == "__main__":
    main()
