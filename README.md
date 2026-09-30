# bitmaskx

集合上的状压工具，纯标准库，无外部依赖。

## 现状

bitmaskx/bitmask.py 提供 MaskDp：

- MaskDp(size)：以元素个数为底座，size 非负整数，否则报错
- full_mask()：全体元素对应的掩码
- mask_of(indices)：把下标序列折成掩码，越界或重复报错
- elements_of(mask)：把掩码展开成升序下标列表
- shortest_hamiltonian(dist, start)：带权完全图上从起点出发访问全部点的最短路径与路径
- shortest_cycle(dist, start)：从起点出发回到起点的最短回路与回路
- min_cover(target, subsets)：用给定子集盖住目标集合的最少个数与一组方案
- min_groups(related)：把元素分成若干组、每组内部两两相容的最少组数与划分
- shortest_hamiltonian_backtrack / min_cover_backtrack / min_groups_backtrack：
  三条独立的递归回溯做法，用于与新路逐项对照
- perm_visits / cover_visits / partition_visits / backtrack_visits：上一次计算的枚举次数

内部对起点之外的全部点枚举全排列算路径与回路，按个数从小到大枚举全部子集组合
判覆盖，递归枚举全部集合划分校验相容，元素个数一多就指数甚至阶乘，但结果正确。

## 问题

最短路径与回路靠全排列枚举，点一多就是阶乘量级；集合覆盖靠组合枚举，子集一多
就是指数量级；划分靠递归枚举全部划分，同样是组合爆炸。三条路各自为政，还没有
任何以位掩码为底座、按掩码从小到大递推的动态规划，也没有计数说明省了多少，新老
两条路之间没有逐项核验，零个或一个元素、元素全选、无覆盖方案、权为零或为负、
并列最优这些边界只能靠肉眼去猜。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_bitmask.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
