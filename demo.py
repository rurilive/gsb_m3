"""WordList 现状演示。

第一段：登记、词频、包含判断、前缀判断与前缀收集。
第二段：预留的前缀树演示位子（见文末注释）。
"""

from pytrie.trie import WordList


def main():
    print("=== 词表 ===")
    wl = WordList()
    for word in ("car", "cart", "care", "cat", "dog", "do"):
        wl.insert(word)
    wl.insert("car")

    print(f"  len            = {len(wl)}")
    print(f"  count(car)     = {wl.count('car')}")
    print(f"  contains(cart) = {wl.contains('cart')}")
    print(f"  starts_with(ca)= {wl.starts_with('ca')}")
    print(f"  words(car)     = {wl.words_with_prefix('car')}")
    print(f"  remove(car)    = {wl.remove('car')}")
    print(f"  count(car)     = {wl.count('car')}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
