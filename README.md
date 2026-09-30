# boruvka

无向带权图最小生成森林的朴素工具，纯标准库，无外部依赖。

## 现状

boruvka/mst.py 用最直白的扫描求最小生成森林：

- check_graph(n, edges)：校验节点数与边表，非法就近报错
- normalize_edges(n, edges)：把边表规范成三元组列表，保留重边与自环
- is_connected(n, edges)：全图是否连成一片
- components(n, edges)：按最小成员编号给出确定的分量划分
- mst_edges(n, edges)：给出所选边的输入下标，按权重再按下标升序
- mst_weight(n, edges)：所选边的总权值
- 异常统一挂在 Erro 下：IllegalArgument、UnknownNode

每一轮都对每个连通分量把整张边表从头到尾线性扫一遍，挑出连到别的分量
最便宜的一条边，加进来，反复若干轮直到加不动。

## 问题

每轮每个分量都要把整个边表重扫，边一多轮数一多，代价就上到平方甚至更高；
已经合并成一片的分量下轮还得再扫，重复劳动占了大头，而结果只是若干条边
与一个总权值。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_mst.py 基线一致（基线一个字不改）
- 新行为另开 tests/test_boruvka.py
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
