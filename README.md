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

- 水位存哪：`WatermarkStore(path)` 把每个确认水位以 `RX1 seq at 长度 payload CRC32` 行追加到同一文件，`flush+fsync` 落盘，保留全部历史点，重启先读最后一个完好点。
- 半截怎么判废：读盘逐行校验魔数、列数、payload 长度与 CRC32，任一不符或序号回退即跳过；半截行没有换行/校验不过，绝不会成为有效水位。
- 先确认后落盘：`StreamRunner` 先 `sink.push()` 拿到下游收妥后的水位，再 `store.save()`，故盘上水位永不超过实际已推位置。
- 丢弃怎么计数：`MemorySink` 对 `seq <= watermark` 的重复或乱序迟到记录丢弃，`discarded`/`stats()["discarded"]` 计数，水位只增不减。
- 阻塞怎么计数：`StreamRunner(max_buffered=n)` 用有界队列隔在取数与推送之间，队列满时 `put` 阻塞、停止从来源取，阻塞次数计入 `progress()["blocked"]`。
