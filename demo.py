"""路径匹配演示。

第一段：段级 glob 的行为（* 不跨段、段数对齐）。
第二段：.gitignore 语义（否定、目录限定、嵌套优先）过滤源码树。
"""

from pathmatch.ignore import IgnoreRules, matched
from pathmatch.match import match

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
build/
!keep.o
docs/**/*.tmp
"""

SRC_IGNORE = """\
# src 局部规则：重新包含 generated.o
!generated.o
"""

IGNORE_TREE = [
    ("main.py", False),
    ("build", True),
    ("build/app.o", False),
    ("src/core/engine.o", False),
    ("src/generated.o", False),
    ("keep.o", False),
    ("docs/a/b/c.tmp", False),
    ("README.md", False),
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

    print("\n=== .gitignore 语义：否定、目录限定、嵌套优先 ===")
    root_rules = IgnoreRules(ROOT_IGNORE, base="")
    src_rules = IgnoreRules(SRC_IGNORE, base="src")
    stack = [root_rules, src_rules]
    for relpath, is_dir in IGNORE_TREE:
        decision, rule = matched(relpath, is_dir, stack)
        kind = "dir " if is_dir else "file"
        if rule is None:
            print(f"  {decision:<7} {kind} {relpath:<24} (无命中规则)")
        else:
            where = rule.base or "."
            print(
                f"  {decision:<7} {kind} {relpath:<24} "
                f"<- {where}/.gitignore:{rule.lineno}: {rule.source}"
            )


if __name__ == "__main__":
    main()
