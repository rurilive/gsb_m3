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
