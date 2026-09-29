# cachely

一个纯标准库的 Python 缓存包，无外部依赖。当前只提供最朴素的无界字典缓存
DictCache：放进去、取出来、命中就把访问计数加一，没有容量上限，也没有淘汰。

## 现状

cachely/cache.py 提供 DictCache：

- DictCache()：直接用一个 dict 存键值，没有容量参数
- get(key)：命中返回 (True, value) 并把访问计数加一，未命中返回 (False, None)
- set(key, value)：直接写入并返回值，键已存在则覆盖，访问计数保留
- access_count(key)：某键累计被命中的次数，从未命中过返回 0
- len() / in：条目数与成员判断

条目只增不减，访问计数只是记着，不参与任何决策。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_cache.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10 及以上

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
