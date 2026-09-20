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

- 水位存哪：`resumex/resume.py` 的 `WatermarkStore` 把每次确认后的水位追加写到指定文件，一行一条 `{"seq", "crc"}`，保留多个历史点，`history()` 取最近 keep 条
- 半截判废：加载时只认以换行结尾且 crc32 校验通过的整行，写一半的尾行、校验失败的行一律丢弃
- 落盘时机：`ResumableRunner` 先 `sink.push()` 拿到下游确认，再把水位落盘，水位只增不减（回退直接报错）
- 续传：启动先读 `store.latest()`，从水位之后取数，已确认的不重喂
- 丢弃计数：序号 ≤ 当前水位（含重复与乱序迟到）或已在未确认缓冲中的记录不入队，`dropped` 计数
- 阻塞计数：未确认缓冲到 `buffer_size` 上限就暂停从来源取数，每暂停一次 `blocked` 加一
