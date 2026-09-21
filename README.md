# slotledger

放号系统在用的多机房名额同步包，纯标准库，无外部依赖。

## 现状

`slotledger/ledger.py` 提供 `Ledger(total, clock=time.monotonic)`，中心名额
账本：

- `grant(site, amount)`：给站点划名额，受剩余量约束，返回实际划到的数量
- `retire(site, amount)`：站点退回没用完的名额，超退自动截住
- `remaining()` / `outstanding(site=None)` / `total()`：查账，恒有
  remaining 加 outstanding 等于 total
- `history()`：动账流水，seq 全局递增
- `set_link(site, up)` / `link_up(site)`：专线状态，断开时该站动账抛
  `LinkDown`

`slotledger/site.py` 提供 `Site(ledger, name)`：朴素站点，`admit(n)` 每放
一个名额就往账本要一个，`blocked_last()` 报停住原因，`released()` 报累计
放行，`in_hand()` 恒为 0。

`slotledger/plan.py` 提供对拍工具：`make_script(seed, ...)` 生成确定性的
事故脚本（各轮到达量加断链时间线），`ideal_admissions(script)` 纯算术算出
上帝视角的放行上界，`playout(script, make_site, on_round=None)` 把脚本交
给多线程跑完。

`slotledger/bench.py` 量吞吐：`measure(make_site, threads, seconds)` 并发
放名额计每秒放行数，`round_trips(ledger, site=None)` 数账本动账次数，
`candidates()` 列出进比对的实现，`python3 bench.py` 打印对比表。

## 问题

每放一个名额一趟账本往返，高峰时账本先被打垮；专线一断，站点一个都放不
出，全在误杀。先放行再异步同步的老路子又超放过，红线是任何时刻累计放行
不许越过总配额。预领批量、断链续放、恢复对账这些都没有。

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 下的基线保持不变（基线一个字不改，必须原样全绿）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 账本记账、朴素站点、对拍与断链事故
python3 -m unittest discover -s tests -v # 行为基线测试
python3 bench.py                         # 并发放名额吞吐对比表
```

## 实现说明

- `slotledger/buffer.py` 的 `BufferSite`：一次 `grant` 划一批进本地，多线程
  加锁扣本地库存，不丢不重，批尽才再跑账本。
- 批大小按消耗快慢自调：量上一批花多久，往目标补给周期靠，夹在
  `min_batch`/`max_batch` 之间，平稳期平均每 8 个名额最多一趟账本。
- 断链就花手里这批，花完如实拒并报 `link_down`；期间不碰账本。
- 线一恢复，下一次放行前先 `Ledger.report(site, seq, used, returned)`
  对账：用了多少、剩多少一并报回，对完才领新批。
- `report` 按站点对账序号幂等，专线重发同一序号不重复动账；报账与在外
  名额对不上直接拒收。
- 收工 `close()` 把囤的一次退干净；账本守恒式扩为
  `remaining + outstanding + used == total`，两边永远对得上。
