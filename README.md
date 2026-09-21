# rackplace

机房里的分区放置器，纯标准库，无外部依赖。

## 结构

- `rackplace/topology.py`：`ClusterTopology` / `Node`，机架分组的节点表，节点带权重。
  节点按上架顺序保留；架上节点走光了，机架也跟着消失
- `rackplace/placement.py`：`Placement` 是"分区 -> 副本节点"的不可变快照；
  `round_robin` 按节点列表平铺切分；`migration_count` 数两份布局之间副本集合变了的那些分区
- `rackplace/manager.py`：`PlacementManager` 管一份布局的来去，`rebalance()` 重排并记住结果，
  `add_node` / `remove_node` 改完拓扑就重排，`current()` 拿最近一次的结果
- `rackplace/verify.py`：`check` 逐分区体检，`summary` 给每节点负载和轻重两极

## 现状

`rebalance` 每次都是照当前节点列表从零轮询一遍，不看上一份布局；
机架信息只挂在拓扑上，放置本身还没用上。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
