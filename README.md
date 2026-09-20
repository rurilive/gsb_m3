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

`radixest/counting.py` 之外，`radixest/estimator.py` 提供
`CardinalityEstimator(bits, seed, exact_limit, dense_threshold=1024)`：
`add` 返回是否首次出现，`count()` 在精确段给精确整数、超出后给线性计数估算，
`error_bound()` 给当前状态下的相对误差上界，`to_dense()`/`to_sparse()` 显式互转，
`a.merge(b)` 返回覆盖并集的新估算器（输入不动）。

## 实现说明

- 哈希用 `blake2b(pickle(seed, key))`，种子参与哈希，固定种子结果可复现。
- 基数不超过 `exact_limit` 时原样存 set，`count()` 精确、误差界为 0；第 `exact_limit+1` 个新 key 把 set 灌进位图并退化为线性计数 `n=-m·ln(零位/m)`。
- 稀疏表示只在 set 里存置位位置；置位数首次达到 `dense_threshold`（含晋升当时与后续 add）自动转稠密，稠密位图为定长 `bytearray`；两种表示都可显式互转，位图内容不变，`count()` 不跳。
- 合并要求 `bits`、`seed` 一致，位图按位或；精确段取两边精确 key 的并集，并集不超过新的 `min(exact_limit)` 时仍给精确值，否则整体退化到位图。
- 误差界按线性计数相对标准差 `sqrt(m·(e^x−x−1))/n`（x=置位比）取 6 倍并叠 0.5% 地板；位图或运算只可能抬高零位占比，所以合并后按合并位图重算，界不大于各分片。
- 置位比达到 0.8（负载约 1.6）超出线性计数有效区间，误差界退化为 100%；亿级基数应按位图位数选型，让负载落回区间内。
