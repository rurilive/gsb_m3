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
- `jqplan/planner.py` 的 `Planner`：`plan(query, stats=None)` 现在直接返回声明顺序

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

`Planner.plan(query, stats)` 拿到新鲜统计时，用行数和列基数估中间结果大小
（每条等值条件按 `1 / max(两边列基数)` 折算选择率），按等值条件把表分成
若干连接组——`Planner.components(query)` 返回各组，组内、组间都按声明
顺序。组内用子集动态规划挑出估计探测行数最小的执行顺序，组之间按声明
顺序叉积；超过十三张表的组退成贪心，保证规划耗时可控（十一张表远在一秒
以内）。

统计缺失、过期（`Stats.stale` 非空）或缺连接列基数时，整体退回声明顺序。
同样的查询加同样的统计，每次得到的计划相同。执行侧完全不动：计划交给
`Engine.execute_plan`，还是嵌套循环，探测行数口径不变。
