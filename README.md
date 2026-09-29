# colstore

纯标准库的内存列式存储雏形，无外部依赖。

## 现状

colstore/column.py 与 colstore/store.py 提供一列整数与若干列凑成的存储：

- Column(name, values)：一列整数，逐值拷一份，非整数立刻报错
- Store(columns)：若干列，列序按首次出现推导，各列长度必须相等
- get、to_list、scan、get_value、get_row：逐值或整列取回，都对外只读
- storage_size：当前存储占用，朴素存储下即元素个数

## 问题

每一列都原样按整数存着，重复很多的列与递增的列占的存储量都跟随机列一样，
扫描只能整列取回，想看一段区间也只能全列解出来再切片，谓词更要等整列取回后逐值判断。

## 目标

在当前基础上补出多种列编码、惰性解码与按需扫描，见任务描述。约束：

- 现有行为与 tests/test_store.py 基线保持一致（基线一个字不改）
- 纯标准库
- 编码后必须能正确解回原值，区间扫描不许把整列都解出来

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）