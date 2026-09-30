# profiledp

网格铺放计数工具，纯标准库，无外部依赖。

## 现状

profiledp/profile.py 提供 ProfileDp：

- ProfileDp(rows, cols, names=None, obstacles=None)：以行数列数与形状表为底座，
  rows、cols 为非负整数且 cols 不超过掩码位数上限，形状名只认 domino_h、
  domino_v 与两种朝向的 L 形（记为 L_a 与 L_b），障碍格为（行，列）二元组且不得越界
- brute_placements(obstacles=None)：逐格全枚举，返回全部铺满方案
- brute_count(obstacles=None)：铺满方案数
- brute_canonical(obstacles=None)：最小规范形，未铺与障碍为点号
- brute_judge(layout, obstacles=None)：逐格判定一个放置列表是否合法
- brute_best(weight, obstacles=None)：枚举全部方案求最小权重和与布局
- independent_brute(obstacles=None)：独立做法一，按格全枚举
- independent_rows(obstacles=None)：独立做法二，状态压缩按行枚举整行掩码
- brute_visit_count / row_visit_count / outline_visit_count / judge_visits：
  上一次计算的枚举次数，轮廓线转移次数基线恒为零

内部对每个最靠前的空格递归尝试全部放置，方案数一大就指数爆炸，但结果正确。

## 问题

逐格全枚举对每个空格逐形状试探，方案数与探测次数都随格子数指数增长；合法判定
逐格重复走一遍；带权最优把全部方案枚举完再挑，没有任何把轮廓线上各格占用状态
压进一个掩码、按格逐行逐列递推的手段，也拿不出计数说明省了多少。两条独立慢速
做法各自为政，与升级路径之间没有逐项核验，空网格、单格、一行一列、障碍格占比
高导致无解、掩码位数达上限、方案数为零、奇数格无法铺满这些边界只能靠肉眼去猜。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_profile.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
