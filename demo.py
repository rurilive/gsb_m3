"""路径匹配演示。

第一段：段级 glob 的行为（* 不跨段、段数对齐）。
第二段：gitignore 风格的 IgnoreRules 过滤（否定、目录限定、嵌套优先）。
"""

import textwrap

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

    print("\n=== .gitignore 语义：否定、目录限定、嵌套规则优先 ===")
    root_rules = IgnoreRules(textwrap.dedent("""\
        # 根目录规则：生成物一律忽略，保留 keep.log
        *.log
        build/
        docs/*.tmp
        !keep.log
        """))
    src_rules = IgnoreRules(textwrap.dedent("""\
        # src/.gitignore：源码目录里只留 main.py
        *.py
        !main.py
        """), base="src")
    stack = [root_rules, src_rules]
    candidates = [
        ("main.py", False),
        ("build", True),
        ("build/out.o", False),
        ("error.log", False),
        ("keep.log", False),
        ("docs/draft.tmp", False),
        ("src/main.py", False),
        ("src/core/engine.py", False),
    ]
    for path, is_dir in candidates:
        status, rule = matched(path, is_dir, stack)
        if rule is None:
            decided = "（无命中规则）"
        else:
            where = rule.base or "."
            decided = f"决定规则 {rule.line!r} @ {where}/.gitignore"
        print(f"  {status:<7} {path:<22} {decided}")


if __name__ == "__main__":
    main()
