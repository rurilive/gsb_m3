# sparsem

纯标准库矩阵包，无外部依赖。当前是稠密基线实现。

## 现状

`sparsem/matrix.py` 提供 `DenseMatrix`，把所有元素（含零）按行列顺序原样存在嵌套列表里：

- `DenseMatrix(rows, cols, data)`：构造一个 rows x cols 的矩阵，data 逐行逐列填入
- `rows()` / `cols()`：形状
- `get(i, j)`：读单个元素，越界抛 `IndexError`
- `set(i, j, value)`：写单个元素，返回自身
- `to_dense()`：返回嵌套列表副本
- `equals(other)`：按元素逐位比较，形状不同即不等

稠密存储的代价很直接：一个 200 x 200 的矩阵，哪怕只有 3 个非零元，也要在内存里放满 40000 个格子。

## 目标（见任务描述）

把 `sparsem` 从稠密存储改成稀疏存储：

- 支持按行与按列的压缩存储（CSR 与 CSC），零元素不落存储
- 由坐标三元组构造，重复坐标按相加合并，越界坐标 fail fast
- 稀疏加法与标量乘，结果仍稀疏且与稠密一致
- 稀疏乘法，结果与稠密口径一致，不许中途整体稠密化
- 转置（CSR 与 CSC 互转）与按行迭代，迭代只访问非零元
- 内存约束：极高稀疏度矩阵的存储非零个数须等于实际非零个数

约束：`tests/test_matrix.py` 一字不改且全绿；新行为另开 `tests/test_sparse.py`；纯标准库；非法三元组与形状不匹配 fail fast，异常继承 `SparseError` 基类。

## 运行

```bash
python3 demo.py                          # 稠密存储演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

（实现后补，10 行以内）
