# quorkit

配置中心选主用的法定人数小包。集群成员由外部注入的 `MemberTable` 描述，
所有时刻来自构造时传入的 clock；纯标准库，无外部依赖，测试不用等真实时间。

一个 `Quorum` 实例代表一个节点：记下自己收到的心跳、维护自己的任期号，
并按当前在册成员里的活跃多数派判断自己能不能当 leader。

## 模块说明

`quorkit/quorum.py`：

- `MemberTable(nodes=())`：在册成员表，提供 `add(node)` / `remove(node)` /
  `nodes()`（返回快照）/ `len(table)` / `node in table`。由外部持有，
  可以同时注入给多个节点，用来模拟各节点看到的成员视图。
- `Quorum(cluster, clock=time.monotonic, timeout=1.0, config=None)`：
  `cluster` 为注入的成员表，`timeout` 为本节点配置的失联超时，
  `config` 为集群商量好的公共配置（如 `{"heartbeat_timeout": 5.0}`）。
- `majority()`：凑够这么多票才算多数派。
- `heartbeat(node, ts, term=0)`：记下 node 在 ts 时刻的心跳，node 在这条
  心跳里声称自己处于 `term` 任期；返回这条心跳是否被采纳。
- `active()`：此刻还活着的节点集合，返回独立快照。
- `elect()`：按多数派把自己选成 leader，票够则任期加一并返回新任期，否则 None。
- `term()`：本节点目前的任期号，初始为 0。
- `negotiated_timeout()`：集群协商出来的失联超时；没协商过就退回本地配置。

`quorkit/__init__.py` 导出 `MemberTable`、`Quorum`。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## Known Issues

以下问题曾导致一次双主事故，现均已修复；记录现象与根因，防止回潮。

1. **多数派门槛在构造时被冻住，不随成员表变化。**
   旧实现把 `len(cluster) // 2 + 1` 在 `__init__` 里算一次存成
   `_quorum_size`。备用节点扩容进来后，老进程仍按扩容前的成员数凑票
   （3 人集群 2 票即当选，扩容成 5 人后 2 票远不足多数），于是少数派
   也敢宣布当选。修复：`majority()` 每次按当前在册成员数动态计算。

2. **活跃判定各按各的本机超时，协商超时形同虚设。**
   `_active()` 用的是构造参数 `self._timeout`，而 `config` 里集群谈好的
   `heartbeat_timeout` 只在 `negotiated_timeout()` 里返回、从不参与判定。
   本机超时配得大的节点会把早已超时的成员仍算成活，与按 5s 判定的节点
   得出两份不同的"活名单"，两边各自凑出自己的多数派、前后脚当选。
   修复：`_active()` 统一改用 `negotiated_timeout()`，未协商时才退回
   本机配置，保证各节点对"谁还活着"看法一致。

3. **旧任期心跳被无条件采纳。**
   旧实现的 `heartbeat()` 完全无视 `term` 参数，任何心跳都刷新该节点的
   最近心跳时刻。上一任 leader 醒过来补发的、带着过期任期号的心跳因此
   被当成有效证据，把本该退位的节点重新"算活"，干扰计票。修复：任期号
   严格单调，`term < 当前任期` 的心跳直接拒绝且不刷新活跃时间；
   `term > 当前任期` 时跟进到新任期。

4. **摘除的成员仍留在计票集合里。**
   旧实现只遍历内部心跳字典 `_seen`，从不对照成员表；节点被运维
   `remove()` 后，其旧时间戳继续参与活跃判定，人数虚高。修复：
   `_active()` 只统计当前仍在册（`cluster.nodes()`）的成员，摘除立即
   生效，重新加入需重新报活。

附带修复：`elect()` 旧实现先把任期加一再点票，选不上也会白涨任期，
   与 docstring "票够就任期加一"不符，且会让随后的同任期心跳被误判为
   旧任期。现在先点票、票够才加任期。

防回归测试见 `tests/test_regression.py`；原有锁定测试
`tests/test_quorum.py` 未改动，应保持全绿。
