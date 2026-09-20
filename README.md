# timewheel

采集 agent 里的定时任务轮：任务按延时挂进环形槽位，时间由调用方手动推进，
到期任务收集进就绪队列，由调用方取出执行（轮子本身不执行任务）。纯标准库；
起始时刻从注入的 clock 取（默认 time.monotonic，测试/演示可用
timewheel.clock.ManualClock 手动拨动）。

## 语义约定（以下为本模块的正式行为定义）

1. **时间模型与回绕定义**
   - 轮子有 slots 个槽、固定步长 tick；内部时刻 now 从 clock() 初始化，
     之后只随 advance(now) 以整 tick 步进
   - add(delay, task)：delay 必须 > 0（否则 ValueError），且不得超过一整圈
     slots * tick（否则 ValueError）；deadline = 当前 now + delay，任务放入
     槽 (cursor + ceil(delay/tick)) mod slots
   - 索引以 slots 为模，**最后一个槽（下标 slots-1）照常参与回绕**
2. **advance(now) 与迟到 tick 语义**
   - now 小于当前时刻 → ValueError；与当前时刻之差不足一个 tick → 不推进
   - 推进时逐槽前进：每跨过一个槽，就把该槽内全部任务按加入顺序追加进就绪队列
   - **一次 advance 跨多个槽（含跨回绕点）时，被跨过的每个槽的任务都必须
     恰好进入就绪队列一次，不提前、不丢失、不重复**；deadline 已过的任务
     照常触发（迟到不豁免）
3. **due()**：返回就绪队列全部任务并清空，顺序与追加顺序一致（即到期先后）
4. **去重边界**：add 返回的句柄彼此独立；**相同 delay 的两次 add 是两个
   不同任务，到期都必须出现**，不因同槽或同 deadline 而合并/覆盖
5. **取消语义**：cancel(handle) 让任务不再执行——**无论它还在槽中，还是
   已进入就绪队列但尚未被 due() 取走**；本次调用完成取消返回 True；句柄
   已取消过、或任务已被 due() 取走时返回 False（幂等，不抛错）

## 运行

```bash
python3 demo.py
```

## 测试报告

测试文件：`tests/test_timewheel.py`（纯标准库 unittest，时序全部由注入的
ManualClock 定死）。运行方式（两种等价，可独立重复）：

```bash
python3 -m unittest tests.test_timewheel -v
python3 tests/test_timewheel.py
```

当前结果：**34 个用例，24 绿 10 红**；红用例均为有意钉住的源码与 README
出入，每条红用例上方注释写明了「README 期望什么 / 实际发生什么」。

- 红 · `RED_AddSlotModulo`（`wheel.py` 的 `add` 槽位取模写成
  `% (slots - 1)` 而非 `% slots`）：整圈 delay 应落最后槽再回绕到槽 0、
  delay=slots-1 应落槽 slots-1、任务应在 deadline 当 tick 触发，实际槽位
  整体错位、任务提前或推迟一整圈；建议改为 `% self._slots`。
- 红 · `RED_AdvanceWrap`（`advance` 回绕分支第二段 `range(0, new_cursor)`
  漏掉落点槽）：一次 advance 跨回绕到槽 2 时落点槽任务在 t=10 不触发、
  整圈后落点槽 0 同样被漏，任务滞留到下一圈，违反「不丢失、迟到不豁免」；
  建议改为 `range(0, new_cursor + 1)`（或统一用单循环按相对步长遍历）。
- 红 · `RED_DedupAndOrder` 同 deadline 覆盖（`_ready` 是以 deadline 为
  键的 dict）：相同 delay 的两次 add 到期应都出现，实际后者按同键覆盖
  前者、第一个任务被静默吞掉；建议就绪队列改为保留全部句柄的列表。
- 红 · `RED_DedupAndOrder` due 排序（`due()` 用 `sorted(self._ready)`
  按 deadline 数值排序）：README 要求按追加顺序返回，实际同槽内 deadline
  不同（ceil 后同槽）的任务被重排；建议就绪队列按 drain/加入顺序直接
  追加、`due()` 保序返回。
- 红 · `RED_CancelReady`（`cancel` 只在槽 bucket 中查找句柄）：任务已进
  就绪队列但未被 `due()` 取走时应可取消并返回 True，实际返回 False 且
  任务仍会被取出执行；建议取消时同时从就绪队列移除。
- 红 · `PropertySmallVsBigAcrossWrap` 与 `PropertyDifferentialFull`
  （性质/对拍暴露的同一批出入）：固定 seed 的 add/cancel/advance 随机交错
  序列与朴素参考实现（按 deadline 排序的列表）对拍，触发顺序、次数、最终
  剩余任务在上述槽位错位、回绕漏槽、同 deadline 覆盖、就绪队列不可取消处
  全部分歧；小步逐 tick 与一次大步推进到同一时刻的触发序列也不一致
  （槽 0 只在大步跨圈时被 drain）。修复以上四处后这些红用例应转绿。

绿色用例覆盖并锁定了 README 的其余全部约定：clock 注入与整 tick 步进、
delay 边界（>0 且 ≤ slots*tick）、ceil 归槽、不足一 tick 不推进、时钟
不可回退、逐槽按序收集、迟到任务照常触发、跨多槽不重不漏（不回绕路径）、
due 取走即清空、句柄独立、取消槽中任务幂等且取走后再取消返回 False、
推进不改变已挂任务 deadline；以及无缺陷子空间内 10 个固定 seed 与朴素参考
实现完全对拍一致（含多槽大步推进与取消交错）。
