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
    root_rules = IgnoreRules(
        """\
# 生成物与脚本默认不跟踪
*.log
*.py
docs/
""",
        base="",
    )
    src_rules = IgnoreRules(
        """\
# 嵌套规则优先：保留入口文件
!main.py
""",
        base="src",
    )
    stack = [root_rules, src_rules]
    for r in stack:
        raws = [rule.raw for rule in r.rules]
        print(f"  规则文件 base='{r.base or '.'}': {raws}")
    for p in TREE:
        status, rule = matched(p, False, stack)
        who = rule.raw if rule else "-"
        print(f"  {status:<8} {p:<22} 决定规则: {who}")


if __name__ == "__main__":
    main()
