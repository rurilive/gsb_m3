# fairlease

按优先级发放租约的公平分配器，纯标准库，无外部依赖。

## 现状

`fairlease/lease.py` 提供 `FairLease`：

- `FairLease(clock=time.monotonic, aging=5.0)`：clock 为注入时钟，aging 为老化窗口秒数
- `request(node, prio, timeout=None)`：登记一条请求并返回凭据 ticket；prio 越小越优先，timeout 为最长等待秒数，None 表示不设上限
- `grant()`：发放一条租约并返回 node，队列里没有可发放的请求时返回 None
- `pending()`：仍会参与下一轮发放的 node 列表，按服务顺序排列
- `cancel(ticket)`：撤销尚未发放的请求，返回是否真的撤掉
- 内部记录每条请求的入队时刻与递增 ticket，ticket 顺序即先来后到

## 契约

- 优先级数字越小越优先，同优先级按先来后到。
- 一条请求从入队起等待达到 aging 即视为老化，排到所有未老化请求前面；多条老化请求之间仍按先来后到。老化保证任何请求在有限时间内被发放。
- `cancel` 之后请求立即出队，不再参与发放。
- 请求等待时间超过 timeout 即作废并移出队列；恰好等于 timeout 的那一刻仍视为有效。

## 问题

线上出现低优先级长期拿不到租约、同优先级乱序、撤单不生效、
超时边界误杀几处毛病。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_fairlease.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 现状复现
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 老化提升：每次发放前以注入时钟计算每条请求的等待时长 `now - arrival`，
  达到 `aging` 即视为老化。老化请求整体排在未老化请求之前，彼此之间按
  ticket（即入队先后）排序。由于等待时长单调增长，任何请求最多等一个
  aging 窗口就会被提到队首，低优先级不会被高优先级持续涌入饿死。
- 同级顺序：未老化请求按 `(prio, ticket)` 排序，ticket 单调递增，因此同
  优先级严格先来后到，与节点名无关。
- 撤单语义：`cancel(ticket)` 直接把请求从队列中删除，立即生效；已撤的
  请求不再出现在 `pending()`，也不会在 `grant()` 中占用发放名额。对不
  存在或已发放的 ticket 撤单返回 False。
- 超时边界：仅当 `now - arrival > timeout` 时请求才作废出队；恰好等满
  timeout 的那一刻仍视为有效，可正常参与发放。
