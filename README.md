# treedpx

树上背包问题的求解器，纯标准库，无外部依赖。

## 现状

`treedpx/core.py` 提供 `TreeKnapsack`：

- `load(nodes, parent)`：载入一棵树，`nodes` 是节点名到重量与价值的映射，
  `parent` 是节点名到父节点名的映射，根节点父节点写 `None`
- `nodes()`：全部节点名，按字典序升序，结果确定
- `parent_of(name)`：某个节点的父节点名，根节点返回 `None`
- `brute_force_best(capacity)`：容量上限下的最大总价值
- `brute_force_selection(capacity)`：一组最优选择，按节点名字典序升序
- `feasible_count(capacity)`：重量不超容量的合法组合数
- `brute_force_scale()`：暴力枚举规模，即 2 的节点数次方

选节点必须先选父节点。求解靠逐组合枚举：把所有节点组合列出来，对每个组合逐一
校验父子约束、累加重量与价值，再取合法且不超容量者中的最大价值。口径直白、结果
确定，但节点一多枚举量就指数膨胀。异常基类是 `TreeError`，输入不合法抛
`TreeInputError`，查询未登记节点抛 `UnknownNode`。

## 问题

暴力枚举随节点数指数增长，稍大的树就跑不动；没有按子树容量合并的状态表，也拿不到
状态表规模与暴力规模的对照；只支持单棵树，不支持森林与多重背包；`state_scale()`
尚未实现。

## 目标

见任务描述。约束：

- `tests/test_core.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 暴力枚举求解演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

（实现后补，10 行以内）
