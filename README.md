# mattree

无向图生成树计数的朴素工具，纯标准库，无外部依赖。

## 现状

`mattree/count.py` 把生成树计数交给暴力枚举：

- `check_graph(n, edges)`：校验节点数与边表，非法就近报错
- `normalize_edges(edges)`：把边表规范成端点对列表，保留重边与自环
- `is_connected(n, edges)`：并查集判断是否连成一片
- `degrees(n, edges)`：度数序列，自环计两次，重边各计一次
- `is_spanning_tree(n, edges)`：边数为点数减一且连通
- `count_spanning_trees(n, edges)`：枚举全部边子集，逐个判定并累计
- `enumerate_trees(n, edges)`：把全部生成树按边子集列出
- 异常统一挂在 `Erro` 下：`IllegalArgument`、`UnknownNode`

## 问题

每数一次生成树，都要把全部边子集枚举一遍，逐个子集判定边数与连通性，
代价随边的条数按二的边数次方增长。完全图边稍多就彻底跑不动，而结论只是
一个整数，中间过程用完即弃。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_baseline.py` 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
