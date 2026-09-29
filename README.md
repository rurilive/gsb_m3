# pytrie

纯标准库的字符串词表，无外部依赖。

## 现状

`pytrie/trie.py` 提供 `WordList`，内部一个词条列表加一个词频字典：

- `insert(word)`：追加一个词，词频加一，返回新词频
- `contains(word)`：词频大于零即视为出现
- `starts_with(prefix)`：是否存在某个词以 `prefix` 为前缀
- `remove(word)`：词频减一，并从列表里删去该词的一个副本
- `count(word)`：返回词频，未登记过返回零
- `words_with_prefix(prefix)`：按插入顺序收集所有带该前缀的词
- `__len__` / `__contains__`

## 问题

所有与前缀有关的查询都在词条列表上线性扫描。词一多，即使前缀只命中少数词，
每次查询仍要看过全部词，代价随词数而不是随前缀长度增长。前缀计数、通配匹配、
最长公共前缀、按前缀取高频词这些能力目前完全没有。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_trie.py` 基线保持一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

（实现后补，10 行以内）
