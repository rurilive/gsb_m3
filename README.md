# lexicon

输入法词库的前缀补全模块，纯标准库，无外部依赖。

## 现状

`lexicon/trie.py` 提供 `Trie`：

- `insert(word, freq)`：收录一个词，重复收录覆盖 freq，空词抛 ValueError
- `complete(prefix)`：返回所有以 prefix 开头的词，freq 降序；同频按词的字典序
- 未命中返回空列表

## 问题

用户手滑打错一两个字母（helo、cary 这类输入）时，补全直接查不到任何词，只能删掉重打。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_trie.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 前缀补全演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 距离计算：DFS 遍历 Trie，沿途维护 prefix 对当前路径的 Levenshtein DP 行（只算增删替换）；每个词的距离取根到该词路径上各行末值的最小值，即 prefix 与该词任意前缀的最小编辑距离。
- 合并去重：精确命中距离记 0，与模糊命中走同一条收集路径，每个词只记录一次。
- 排序键：`(距离升序, freq 降序, 词字典序)`；k=0 时只有精确前缀命中（距离全 0），严格退化为现有行为。
- 剪枝：当路径最小距离与当前 DP 行最小值都超过 k 时，子树不可能再命中，直接跳过。
