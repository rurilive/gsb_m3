# resumex

把上游记录按批喂给下游的搬运器，纯标准库，无外部依赖。

## 现状

`resumex/stream.py` 提供来源、下游与搬运器三件套：

- `MemorySource(records=())`：内存来源，`records` 是可迭代的 `(seq, payload)`，序号须严格递增
  - `append(seq, payload)` 追加一条，序号必须大于已有最大序号
  - `fetch(after_seq, limit)` 取序号大于 `after_seq` 的至多 `limit` 条，按序号递增返回 `Record` 列表
  - `latest_seq` 是最大序号（空为 0），`len(source)` 是条数
- `MemorySink()`：内存下游，`push(records)` 接收一批并返回接收后的水位；`watermark` 是已收到的最大序号，`received()` 按到达顺序返回快照，`stats()` 汇总批数、条数与水位
- `StreamRunner(source, sink, batch_size=2, clock=time.monotonic)`：`run()` 逐批取数推送直到来源没有新记录，返回本次推送条数；`progress()` 返回 `last_seq` / `pushed` / `batches` / `last_at` 快照，`clock` 为注入时钟

进度只活在内存里，进程一停就没了；下游按到达顺序照单全收，不认水位。

## 问题

搬运器重启后从头发，下游重复收下已经处理过的记录。

## 目标

见任务描述。约束：

- 现有方法与 `tests/test_stream.py` 基线行为保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 按批推送演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 水位存哪：`resumex/checkpoint.py` 的 `WatermarkLog` 把确认水位追加到行式日志，保留最近 `keep` 个点，超了先写临时文件再 `os.replace` 原子压缩。
- 半截怎么判废：每行 `版本\t序号\t时间戳\tsha1(序号+时间戳)`，读回只认四段齐全、校验通过的行，半截/损坏尾行直接跳过，水位停在上一处完好值。
- 先确认后落盘：`StreamRunner` 启动先 `load()` 水位并按水位之后取数；下游 `push` 返回收妥水位后才 `commit()`，且序号只增不减。
- 丢弃怎么计数：`WatermarkSink` 把 `seq <= watermark` 的重复与乱序记录一律丢弃，条数累计在 `dropped`（见 `stats()`）。
- 阻塞怎么计数：`buffer_size > 0` 时取数/推送走有界队列，缓冲满即停止取数，阻塞次数记 `progress()["blocked"]`、累计等待时长记 `blocked_for`。
