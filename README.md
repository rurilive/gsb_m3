# editlab

字符串差异工具，纯标准库，无外部依赖。

## 现状

`editlab/diff.py` 提供 `HammDiff`，只做等长字符串的逐位比较：

- `diff_count(a, b)`：两串长度必须相等，否则抛 `LengthMismatchError`；逐位统计
  不同字符的个数
- `common_positions(a, b)`：同样要求等长，返回字符相同的下标列表
- 异常统一从 `EditError` 派生，`LengthMismatchError` 是其中之一

没有插入、没有删除、没有替换建模，没有编辑距离，也没有对齐或回溯。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_diff.py` 基线保持一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
