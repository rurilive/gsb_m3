"""路径匹配演示。

第一段：段级 glob 的行为（* 不跨段、段数对齐）。
第二段：用 .gitignore 风格的 IgnoreRules 过滤同一批路径，
展示 ignored/allowed 与决定性规则（含否定、目录限定、嵌套优先）。
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

    print("\n=== .gitignore 风格忽略规则（逐层评估、深者优先） ===")
    root_rules = IgnoreRules(
        "# 生成物\n*.log\nbuild/\nassets/**\n",
        base="",
    )
    src_rules = IgnoreRules(
        "# src 自己的规则：保留 engine.log\n!engine.log\n",
        base="src",
    )
    stack = [root_rules, src_rules]

    dirs = {"assets", "src", "src/core", "src/util", "docs", "build"}
    extra = [
        ("src/engine.log", False),   # 被 src 层否定规则救回
        ("src/build.log", False),    # 仍被根规则忽略
        ("build", True),             # 目录限定 build/
        ("assets", True),            # 目录本身不被 assets/** 命中
        ("assets/logo.svg", False),  # 目录内容被忽略
    ]
    entries = [(p, p in dirs) for p in TREE] + extra
    for path, is_dir in entries:
        status, rule = matched(path, is_dir, stack)
        tag = "IGNORED" if status == "ignored" else "ALLOWED"
        decided = repr(rule) if rule is not None else "（无命中）"
        print(f"  {tag:<8} {path:<20} 决定规则 {decided}")


if __name__ == "__main__":
    main()
