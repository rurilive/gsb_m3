# areaunion

轴对齐矩形集合工具包，纯标准库，无外部依赖。

## 现状

areaunion/area.py 提供 RectSet：

- RectSet(rects=())：以四元组列表为底座，每个矩形是（左，下，右，上），
  四个端点是非布尔整数且左端不大于右端、下端不大于上端，否则在构造时拒绝
- cell_count()：把横纵坐标各自离散化，报出正面积小格的个数，是坐标数量的平方
- union_area()：覆盖至少一次的并集面积，逐小格逐矩形判定，遇覆盖即停
- area_at_least(k) / area_exactly(k)：至少 k 次与恰好 k 次的面积，逐小格把矩形全数一遍
- perimeter()：并集边界总周长，从覆盖布尔矩阵上数水平边与垂直边各自的分界
- covers_point(x, y) / coverage_count_at(x, y) / is_covered(x, y)：逐矩形判定
- independent_brute_area() / independent_brute_area_at_least(k) /
  independent_brute_perimeter()：三条各自独立的逐格慢速做法
- judge_count() / node_access_count()：最近一次逐格判定次数与线段树结点访问次数，
  扫描线路径基线恒为零

内部所有面积与周长能力都先离散化再逐小格判定，小格数是坐标数量的平方，
矩形一多就慢，但结果正确。

## 问题

求并集面积时对每个小格逐个矩形去判，判定次数与小格数、矩形数之积成正比，
而小格数又是坐标数量的平方，坐标一多就是四次方量级；求至少 k 次与恰好 k 次的
面积同样逐小格把全部矩形数一遍；求周长也在离散格上逐格找分界；逐点判定逐矩形
扫一遍。既没有按横坐标扫描、纵坐标建线段树维护被覆盖长度的手段，也拿不出任何
计数说明更聪明的做法省了多少，升级路径与朴素路径之间没有逐项核验。空矩形集、
单矩形、矩形退化为一条线或一点、零面积矩形、完全包含、完全分离、刚好相邻、
坐标含负值、重复矩形、重叠次数恰好为 k 这些边界只能靠肉眼去猜。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_area.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
