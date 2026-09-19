"""lexicon 现状演示。

第一段：小词库的前缀补全与 freq 排序。
文末注释：预留的模糊补全演示位子。
"""

from lexicon.trie import Trie

WORDS = [
    ("carry", 90),
    ("carrion", 20),
    ("card", 70),
    ("care", 60),
    ("hello", 100),
    ("help", 80),
    ("helicopter", 10),
    ("world", 95),
]


def main():
    t = Trie()
    for w, f in WORDS:
        t.insert(w, f)

    print("=== 前缀补全（按 freq 降序） ===")
    for p in ["car", "hel", "w", "helo"]:
        print(f"  complete({p!r}) -> {t.complete(p)}")

    print()
    print("=== 模糊补全（手滑错拼，fuzzy=1） ===")
    for p in ["helo", "cary"]:
        print(f"  complete({p!r})          -> {t.complete(p)}")
        print(f"  complete({p!r}, fuzzy=1) -> {t.complete(p, fuzzy=1)}")


if __name__ == "__main__":
    main()
