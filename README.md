# waitgraph

任务调度器的等待图库：登记谁在等谁手里的资源，回答有没有死锁、环上是谁。
纯标准库。

## 用法

```python
from waitgraph import ResourceRegistry

reg = ResourceRegistry()
reg.acquire(1201, "index")     # True：当场拿着
reg.acquire(1202, "index")     # False：排队等 1201 放
reg.health()                   # {"deadlocked": False, "cycle": []}
reg.release(1201, "index")     # 返回 1202，资源交给队头
```

- `ResourceRegistry(detector=None)` 等待关系的事实来源
  - `acquire(pid, resource)` 空着当场持有返回 True，被占进队等待返回 False；
    自己已经拿着或者已经在等同一个资源抛 `AlreadyHeld`
  - `release(pid, resource)` 放掉自己拿的资源，队头接手并返回接手者 pid；
    没拿着抛 `NotHeld`
  - `drop(pid)` 进程失联（崩溃、断连）：它排的队作废，它手里的资源直接
    收回不转交，等着这些资源的进程一并作废，返回作废的 `(pid, resource)`
  - `holder` / `waiters` / `pending` / `waits` / `holds` 查当前状态，
    `waits()` 是权威等待边 `(pid, resource, holder)`
  - `health()` 给运维探针：`{"deadlocked": 布尔, "cycle": 成员列表}`
  - `load_state(holds, waits)` 启动时从快照整体恢复，不做逐条检测
- `DeadlockDetector` 检测器，registry 每次等待关系变动都会喂事件给它
  （`note_wait` / `note_wake` / `note_drop`，启动加载走 `rebuild`）
  - `deadlocked()` 有没有死锁，`cycle_members()` 环上成员
  - `stats()` 检测过程的访问计数（遍历和整图枚举碰到的节点数），
    `reset_stats()` 归零，压测单次变动的开销时用它观测
- `waitgraph.oracle.FullScan(registry)` 全量参考：每次现读权威登记从零算，
  报告规则固定，作为检测器行为的对拍基准
- `WaitGraph` 底层拓扑与遍历原语（`walk` / `reachable` / `holders`），
  节点展开计入 `visits`，不带业务语义

## 运行

```bash
python3 demo.py                           # 现状演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```

## 复盘：误报与卡顿是怎么来的，怎么修的

上量后运维碰到的四类问题，根子都在旧版检测器：它只在 `note_wait` 后
全图重扫一次，而且把结论缓存下来。

- **环解开了还报警**：`note_wake`（资源转交）和 `note_drop`（进程失联）
  删完边从不重算，`_deadlocked` / `_members` 保持上一次的旧结论。
  现在每次变动事件结束都只按当前图刷新一次判定，删边立刻解除。
- **先后互等被报成环、幽灵边 + pid 复用摘不干净**：旧 `note_drop` 只删
  失联进程作为等待者的出边，别人等它的入边全部残留。图底层新增
  `remove_involving(pid)`，失联进程的出边、入边一次摘净；检测器不再
  有任何跨事件的边残留，历史互等关系自然不会诈尸。
- **环成员混进链条上游、报告随变动历史漂移**：旧 DFS 撞回边时把整条
  搜索路径都报成环（应该从回边落点截断），起点和后继又按登记顺序而非
  pid 升序。现在环成员就是真正成环的强连通分量内节点，截取与旋转规则
  和 `oracle.FullScan` 逐字一致（升序根、升序后继、回边落点截断、旋到
  最小 pid 打头），同一张图无论经历什么事件序列报告恒等。
- **十万节点每来一条边重扫整图**：旧实现每条 `note_wait` 都枚举全部
  节点逐根 DFS，单次几十毫秒、访问计数随规模线性上涨。现在检测器增量
  维护强连通分量：
  - 加边：只在旧图上从两端各做一次局部 BFS，确认闭环才把受影响分量
    合并；不闭环时分量不变，什么都不重算；
  - 删边：跨分量的边删除不影响 SCC，只有分量内边才在该分量内部重算；
  - 判定：没有成环分量时结论直接为空；有成环分量时，从环节点反向 BFS
    找到能到达环的最小 pid，再按 oracle 规则做一次只涉及环附近节点的
    DFS 取环。

效果：十万节点、八万条边的链式图上，闭环/解环/中段加边/进程失联的
单次变动连带 `health()` 访问计数稳定在几十以内（不随节点数增长），
单次耗时从十几毫秒降到亚毫秒；`tests/test_deadlock_fixes.py` 用随机
事件序列每一步与 `FullScan` 对拍判定、环成员和底层图，钉死回归。
