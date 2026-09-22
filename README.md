# jqplan

数据平台的小查询引擎，纯标准库，多表等值连接全在内存里跑。

## 结构

- `jqplan/table.py` 的 `Table`：行是值元组，`insert` / `insert_many` / `rows` /
  `row_count` / `distinct`，每次写入推进 `revision`
- `jqplan/engine.py` 的 `Query` / `Plan` / `Engine`：`Query` 声明参与的表、等值条件
  （表名对，列名对）和输出列；`Engine.execute` 按声明顺序执行，
  `Engine.execute_plan` 按计划给的顺序执行，两者都返回 `ExecutionResult`，
  里面有 `rows`、`rows_scanned`（探测行数）和 `order`
- `jqplan/stats.py` 的 `Stats`：`Stats.collect(tables)` 扫一遍表，得到行数、各列基数
  和采集时的 `revision`；`stale(tables)` 列出对不上的表名
- `jqplan/planner.py` 的 `Planner`：`plan(query, stats=None)` 拿统计估代价、
  重排连接顺序；`components(query)` 给出条件图里连不上的各个连接组

输出列的顺序跟着查询声明走，跟执行顺序无关；条件在涉及的两张表都进入前缀之后
立刻参与过滤。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py                           # 执行顺序与探测行数演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```

## 连接顺序规划

`Planner.plan(query, stats)` 拿到统计快照后，用各表行数和连接列基数
（选择率取 `1 / max(两侧基数)`）估计每个执行前缀的中间结果大小，
按 `Engine` 探测行数的口径给候选顺序估代价：

- 条件图里连不上的表先由 `Planner.components(query)` 分成若干连接组，
  组内用子集动态规划求估计代价最小的顺序（组超过 12 张表时退为贪心），
  组与组之间按叉乘代价排序后拼接成最终计划
- 统计没给、缺表、缺连接列基数，或者快照跟表对不上（`Stats.stale` 非空），
  都整体退回查询的声明顺序，跟 `Engine.execute` 的原行为一致
- 同样的查询加同样的统计必出同样的计划；估计和重排只发生在规划阶段，
  执行方式与 `rows_scanned` 的口径不变

小表集上可以跟穷举全排列的最优探测行数对拍（见
`tests/test_join_order.py`），十一张表时规划耗时在毫秒级。
