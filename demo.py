"""路径匹配现状演示。

第一段：段级 glob 的行为（* 不跨段、段数对齐）。
第二段：把源码树里的一批路径按几种 pattern 逐条过一遍。
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

    print("\n=== .gitignore 语义：IgnoreRules 逐层评估 ===")
    root_rules = IgnoreRules("""\
# 根 .gitignore：生成物与日志
build/
*.log
!important.log
docs/**/draft.md
""")
    src_rules = IgnoreRules("""\
# src/.gitignore：生成的代码，但保留手写的
gen_*.py
""", base="src")
    rule_stack = [root_rules, src_rules]
    entries = [
        ("build", True),
        ("build/app.o", False),
        ("error.log", False),
        ("important.log", False),
        ("docs/v1/draft.md", False),
        ("src/gen_util.py", False),
        ("src/main.py", False),
        ("main.py", False),
    ]
    for path, is_dir in entries:
        status, rule = matched(path, is_dir, rule_stack)
        if rule is None:
            decided = "无命中规则"
        else:
            where = rule.base if rule.base else "<根>"
            text = ("!" if rule.negated else "") + rule.text + ("/" if rule.dir_only else "")
            decided = f"规则 {text!r}（{where} 第 {rule.lineno} 行）"
        print(f"  {status:<8} {path:<20} {decided}")


if __name__ == "__main__":
    main()
