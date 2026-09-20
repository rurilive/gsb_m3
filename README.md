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

以下四类现象曾在一次双主事故中同时出现，根因均已修复，
`tests/test_quorum_regression.py` 按当时时序回放锁死了修复后的行为。

1. **多数派门槛在构造时写死，扩容后按老成员数凑票。**
   旧实现 `__init__` 里把 `len(cluster) // 2 + 1` 缓存成
   `_quorum_size`，此后成员表再怎么增减都不重算。备用节点把
   集群从 3 扩到 5 后，老进程的门槛仍停在 2，五人集群里活两个
   就敢宣布当选。修复后 `majority()` 每次按当前在册成员动态计算，
   `elect()` 也直接读取同一动态门槛。
2. **活跃判定用本机超时，而不是集群协商超时。**
   旧实现 `_active()` 按构造参数 `self._timeout` 判断心跳是否过期，
   `config["heartbeat_timeout"]` 虽然有 `negotiated_timeout()`
   暴露出来却没人用。本机配 30s 的节点和配 5s 的节点对“谁还活着”
   看法对不上，各自看到一个“多数派”并前后脚当选，形成双主。修复后
   `_active()` 一律以 `negotiated_timeout()` 为准，没协商过时才退回
   本地配置。
3. **旧任期的心跳照样被采纳，任期不会往回走。**
   旧实现 `heartbeat()` 完全不看 `term` 参数，任何心跳都无条件刷新
   活跃时间戳。老 leader 停顿多任后醒过来，带着早就过期的任期号
   补发心跳，也会把本该退位、已经超时的节点重新算活，等于让任期
   倒退。修复后任期严格单调：`term < 当前任期` 的心跳直接拒绝，
   不更新任何状态；`term > 当前任期` 时按 Raft 惯例对齐到新任期。
   同时 `elect()` 改为票够才把任期加一（与文档契约一致），失败的
   选举不再凭空抬高任期门槛。
4. **摘除成员的旧时间戳长期留在计票集合里，人数虚高。**
   旧实现 `_active()` 只遍历内部 `_seen` 心跳表、从不回查在册成员
   表，节点被 `remove()` 后它留下的旧心跳时间戳仍在超时窗口内继续
   投票。修复后活跃集合取“心跳新鲜”与“当前在册”的交集，摘除
   立刻生效；从未在册节点的心跳也永远不会计入。
