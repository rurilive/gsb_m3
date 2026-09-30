# editpath

编辑距离与序列对齐工具，纯标准库，无外部依赖。

## 现状

`editpath/core.py` 提供一份朴素实现 `EditPath`，全部能力都靠枚举：

- `edit_distance(a, b)`：把 a 改成 b 的最少单字符增删改次数，对每一步把
  删除、插入、替换三种操作各递归展开一次，同一对前缀被反复重算
- `weighted_distance(a, b, replace_cost, delete_cost, insert_cost)`：三种操作
  各自带权重的代价，仍靠逐步枚举递归
- `indel_distance(a, b)`：只允许插入删除时的最少步数，等于两串长度之和减
  两倍最长公共子序列长度
- `lcs_length(a, b)`：最长公共子序列长度，枚举第一个串的全部子序列
- `lcs_substring(a, b)`：最长公共子串长度，枚举第一个串的全部子串
- `lcs_prefix(a, b)`：最长公共前缀长度，从首字符逐个往下比
- `EditPathError`：所有错误的基类，继承 `Exception`；`TypeMismatchError`
  是其中之一

## 问题

编辑距离走的是带记忆缺失的递归，三分支高度重叠，长度一长状态数就指数级
膨胀；最长公共子序列与最长公共子串都在枚举组合，同样很快卡死。基线只给
距离这一个数字，既回溯不出具体的编辑操作序列，也没有加权编辑的独立验算
路径，最长公共子序列与最长公共子串也没有动态规划口径可用。

## 目标

见任务描述。约束：

- `tests/test_core.py` 是基线，一字不许改且必须全绿
- 新行为另开 `tests/test_dp.py`
- 纯标准库，无第三方依赖

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
