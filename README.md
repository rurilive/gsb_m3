# mvjoin

看板的数据层：内存表吃变更流，视图引擎出分组聚合结果。纯标准库，无外部依赖。

## 变更流

一条变更一个 dict，按到达顺序喂给 `Dataset.apply`：

```python
{"seq": 7, "table": "orders", "op": "insert", "before": None,  "after": {"order_id": 101, ...}}
{"seq": 8, "table": "orders", "op": "update", "before": {...}, "after": {...}}
{"seq": 9, "table": "orders", "op": "delete", "before": {...}, "after": None}
```

`seq` 由上游发放，全局单调递增，同一条变更重发时 seq 不变。主键列的值不变，
`before` 与 `after` 的主键一致，连接键之类的普通列随便改。`ChangeLog` 是攒变更流的
小工具，seq 从 1 自增。

## 模块

- `mvjoin/tables.py`：`Table`（按主键存行，拿出去的都是副本）、`Dataset.apply()`
  （按变更流更新，对不上的变更抛 `TableError`）、`ChangeLog` 与三个造变更的函数
- `mvjoin/spec.py`：`ViewSpec` 描述一张视图，`Join` 描述等值连接。
  单表视图的列名不带前缀，连接视图写成 `表名.列名`；指标是
  `(名字, 聚合, 列)` 三元组，聚合支持 `count` 与 `sum`；`where` 是可调用对象，
  连接视图拿到的是两表字段拼起来的一行
- `mvjoin/full.py`：`FullView(spec).recompute(dataset)` 全量重算一遍，
  `result()` 给最近一次的结果副本。连接键为 None 的行不参与连接，
  右表同键多行时左表逐行配对（配对就都算数），组里没有任何配对后
  这个组从结果里消失。`refreshes` 与 `last_pairs` 记录重算次数和最近一次配对数量

## 目标

见任务描述。

## 运行

```bash
python3 demo.py                          # 变更流落库 + 全量重算 + 逐条步进测速
python3 -m unittest discover -s tests    # 既有行为基线测试
```
