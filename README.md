# gtheor

公平组合游戏有向图局面工具包，纯标准库，无外部依赖。

## 现状

gtheor/graph.py 提供 GameKit，把一道公平组合游戏描述成有向图，结点是局面，
边是一步合法走法：

- outcome(graph, start)：起点局面的赢输，对每个后继递归枚举并做赢输判定，
  不记忆化，已算过的局面再次遇到也照重算，反复重入同一局面
- winning_move(graph, state)：按后继顺序返回第一个一步制胜的走法
- min_moves(graph, start)：先手必胜时的最少取胜步数，必败局面返回 None
- grundy(graph, start)：起点格林数，后继格林数集合的最小不出现非负整数
- xor_outcome(games)：多个独立子游戏起点格林数取异或后的胜负
- all_outcomes(graph)：对图中每个结点逐个判赢输
- heap_game(size, max_take)：造一张取石子减法游戏图
- expansions：本次调用朴素递归重入局面的次数
- GameErro：异常基类，下分 GraphErro 与 StateErro

## 问题

每个后继都用同一条朴素递归从头再算，不记忆化也不按拓扑自底向上，同一个局面
被反复重入，局面一多就指数级重复展开；取胜所需的最少步数、并列多条制胜步的
重建、多个子游戏异或合并都建立在同一条重复展开之上，规模稍大就跑不完，也拿
不出任何计数说明更聪明的做法省了多少。有环导致无法终止时口径不清，边界情形
更无从对照。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_graph.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
