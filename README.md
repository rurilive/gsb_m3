# qsketch

埋点链路的延迟统计库，纯标准库，无外部依赖。

## 模块

- `qsketch/samples.py`：`SampleSet`，全量留样本。`add(value)` 收一条，
  返回当前样本数；样本转成 float 存，bool、nan、inf 一律拒绝。
  `quantile(q)` 全量排序后线性插值，`cdf(x)` 给小于等于 x 的占比，
  `mean` / `minimum` / `maximum` / `stats` / `count` / `values` 是其余读数。
  空集合上取读数抛 `EmptySetError`。`to_sample` / `check_quantile` /
  `quantile_of_sorted` 是模块里的公共助手。
- `qsketch/shards.py`：`ShardSet`，按分片记账。`add(shard, value)` 在分片
  不存在时新建（分片名必须是 str），`count(shard)` / `values(shard)` 看单片，
  不给分片名就跨片；`quantile(q)` 把各片样本拼起来精确计算，`names()` 给
  排好序的分片名，`merge(other)` 并两份账本，返回新对象，两边不动。
- `qsketch/codec.py`：`dump(obj)` / `load(data)` 走 JSON bytes，顶层带
  `fmt` 格式号（当前 1）；`save(obj, path)` / `read(path)` 落文件。
  同一份对象落盘两次字节一致；内容不合规一律抛 `FormatError`。
- `qsketch/errors.py`：`SketchError` / `EmptySetError` / `FormatError`。

## 运行

```bash
python3 demo.py                           # 全量样例、分片账本、落盘读回
python3 -m unittest discover -s tests     # 行为基线
```

## 目标

见任务描述。约束：现有接口与 `tests/` 基线保持不变（基线一个字不改），
纯标准库，运行环境不装任何三方包。
