# lexicon

输入法词库的前缀补全模块，纯标准库，无外部依赖。

## 现状

`lexicon/trie.py` 提供 `Trie`：

- `insert(word, freq)`：收录一个词，重复收录覆盖 freq，空词抛 ValueError
- `complete(prefix, fuzzy=None)`：`fuzzy=None` 精确前缀补全；`fuzzy=k`（非负整数）模糊补全
- 精确补全按 freq 降序、同频按词的字典序；未命中返回空列表

## 问题

用户手滑打错一两个字母（helo、cary 这类输入）时，补全直接查不到任何词，只能删掉重打。

## 模糊补全

`complete(prefix, fuzzy=k)` 中 k 为非负整数：编辑只算增、删、替换；候选词的
命中距离取 `prefix` 与该词**任意前缀**的最小编辑距离，距离不超过 k 即命中。
`fuzzy=None` 保持精确前缀补全；`fuzzy=0` 严格等价于精确前缀补全。

## 约束

- 现有行为与 `tests/test_trie.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 前缀补全演示
python3 -m unittest discover -s tests -v # 行为基线测试
```


## 实现说明

- 沿 Trie 路径做 Levenshtein 动态规划：进入子节点时由父行递推新行，行末列即 `prefix` 对当前路径前缀的距离。
- 候选词在某个节点成词时，命中距离取从根到该节点路径上行末列的历史最小值（即“任意前缀”口径）。
- 精确命中（距离 0）与模糊命中在同一次遍历中产出，按词写入 dict，天然合并去重。
- 完整 `prefix` 的距离与 DP 行最小值都大于 k 时，对应子树直接剪枝。
- 精确模式排序键为 `(-freq, word)`；模糊模式排序键为 `(distance, -freq, word)`，即距离升序、freq 降序、字典序兜底。
