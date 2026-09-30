"""stablematch 现状演示。

第一段：拿一份小规模偏好表，看现有穷举实现给出的稳定配对。
第二段：预留的迭代演示位子（见文末注释）。
"""

from stablematch.core import all_stable, first_unstable, normalise, stable_pairing


MEN = ["ann", "bob", "cid"]
WOMEN = ["dee", "eve", "fay"]
MEN_PREFS = {
    "ann": ["eve", "dee"],
    "bob": ["fay", "eve"],
    "cid": ["dee", "fay"],
}
WOMEN_PREFS = {
    "dee": ["bob", "cid"],
    "eve": ["cid", "ann"],
    "fay": ["ann", "bob"],
}


def main():
    print("=== 稳定配对（现有能力） ===")
    pairing = stable_pairing(MEN, WOMEN, MEN_PREFS, WOMEN_PREFS)
    print("  stable_pairing() -> " + str(pairing))
    men, women, mprefs, wprefs = normalise(MEN, WOMEN, MEN_PREFS, WOMEN_PREFS)
    print("  first_unstable() -> " + str(first_unstable(pairing, mprefs, wprefs)))
    print("  稳定方案个数     -> " + str(len(all_stable(men, women, mprefs, wprefs))))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
