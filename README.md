# radixest

埋点链路的去重计数库，纯标准库，无外部依赖。

## 现状

`radixest/counting.py` 提供精确的 `DistinctCounter`：

- `DistinctCounter()`：空计数器，不同 key 原样存在内部 set 里
- `add(key)`：记一个 key，首次出现返回 `True`，重复出现返回 `False`；key 需可哈希
- `count()`：当前不同 key 的个数
- `key in counter` 判断某个 key 是否出现过，`reset()` 清空
- 内部一把锁保护，单次操作在多线程下安全

结果精确，代价是内存随不同 key 数线性增长。

## 问题

分钟级去重流的基数已经到亿级，精确计数器把内存顶穿；分片各数各的再把结果相加，同一个 key 落在多片会被重复入账。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_counter.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 精确计数演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
