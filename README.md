# subsetconv

集合函数卷积工具包，纯标准库，无外部依赖。

## 现状

`subsetconv/convolution.py` 提供 `SetFunction`，把一个数组当作集合函数，
下标是集合的比特掩码（长度必须是正整数二次方）：

- `or_convolve(other)`：或卷积，结果下标等于两下标按位或
- `and_convolve(other)`：与卷积，结果下标等于两下标按位与
- `xor_convolve(other)`：异或卷积，结果下标等于两下标按位异或
- `subset_convolve(other)`：不交并子集卷积，只累计两下标不相交的情形
- `pair_count()`：朴素逐对累加的下标对数量
- `size` / `as_list()` / `len()`：规模与取值查询

四种卷积都是枚举一个下标再枚举另一个下标、逐对累加，规模到四次方量级。
长度非法抛 `InvalidLengthError`，两数组长度不一致抛 `LengthMismatchError`，
两者都继承 `ConvolutionError`。

## 问题

朴素逐对累加在每个下标对上做一次运算再累加，下标对是二次方，整体是四次方
量级；规模一大就明显变慢。也没有快速变换口径、没有与快速路径可互印证的独立
做法、没有不交并的分层求法，更没有由卷积结果反推原数组或判断结果可达的能力。

## 目标

在保留上述朴素路径的前提下，接入快速沃尔什变换与独立印证口径、不交并分层求法
与反推校验，见任务描述。约束：

- `tests/test_convolution.py` 基线一个字不改，必须原样全绿
- 新行为另开测试文件
- 纯标准库
- 朴素路径不许删，新老两条路对同一批数据事实必须逐项一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
