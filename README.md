# treeindset

在树上求最大独立集与最小点覆盖的朴素工具，纯标准库，无外部依赖。

## 现状

`treeindset/treesolve.py` 提供 `TreeSolve`：

- `add_edge(u, v)`：在两个已知顶点之间连一条无向边，重复加同一条边不报错
- `edges()` / `neighbors(v)` / `edge_count()`：去重排序后的边、邻居、边数
- `max_independent_set()` / `min_vertex_cover()`：枚举全部选法逐边核对后取方案
- `independent_size()` / `cover_size()`：只给大小
- `is_independent_set(vertices)` / `is_vertex_cover(vertices)`：按定义判定

求任一答案都要枚举每个顶点的选与不选共二的点数次方种选法，每一种再拿全部边
逐对核对；并列时先比大小再看顶点编号序列，取编号较小的那一组。异常继承 `Erro`
基类，再分入参错误与未知顶点两个子类。

## 问题

求解代价绑死在顶点个数上。顶点一多，枚举的选法就按二的幂增长，每个选法又要
再扫一遍全部边，二十来个顶点就慢到没法用；子结构的最优解完全没法复用，改动
一条边就得推倒重来。

## 目标

见任务描述。约束：

- `tests/test_treesolve.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库，异常统一继承 `Erro` 基类

## 运行

```bash
python3 demo.py                          # 枚举选法求独立集与点覆盖
python3 -m unittest discover -s tests    # 行为基线测试
```

（实现后补，10 行以内）
