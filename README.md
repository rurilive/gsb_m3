# bitlib

位集合工具包，纯标准库，无外部依赖。用来存一批互不相同的整数下标，
做置位、清零、取值与集合运算。

## 现状

- `bitlib/bitset.py`：`BoolBits(length)` 用布尔列表存位集合，置位 `set(i)`
  与清零 `clear(i)` 直接改列表里的某一格，`get(i)` 取某一位，`count()` 数
  置位总数，`union()` 与 `intersection()` 逐位循环算与或，`to_list()` 列出
  全部置位下标。下标越界、位长为负、两个集合位长不一致都会抛 `BitlibError`。
- `bitlib/__init__.py`：导出 `BitlibError` 与基线类 `BoolBits`。

位是一位一个布尔值铺成一个列表，所以存储开销与位长成正比地按位增长；
两个集合做一次与或要逐位循环一遍，位长越大越慢；也还没有异或、差、补、
移位、切片、找位这些操作。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
