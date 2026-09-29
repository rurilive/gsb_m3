# quadrex

纯标准库的点集空间查询包，无外部依赖。

## 现状

quadrex/points.py 提供顺序扫描的点集 LinearPoints：

- LinearPoints(points=None)：建立一个点集，可传入一组初始点
- insert(x, y)：插入一个点，已存在则不重复加入
- remove(x, y)：删掉一个点
- contains(x, y)：点是否在集合里
- query_rect(xmin, ymin, xmax, ymax)：返回闭矩形内的全部点，按 (x, y) 升序
- points()：当前全部点，按 (x, y) 升序

点存在一个列表里，矩形查询逐个点判断是否落在范围内，没有树、没有划分、没有
层次。非法坐标与非法矩形抛 QuadError 的子类。

## 目标（见任务描述）

见任务描述。约束：

- 现有行为与 tests/test_points.py 基线一致（基线一个字不改）
- 纯标准库
- 新行为另开 tests/test_quadtree.py，不改动基线测试文件

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
