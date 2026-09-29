# suffixx

纯标准库的后缀查询工具，无外部依赖。

## 现状

suffixx/table.py 提供朴素后缀工具 NaiveSuffix：

- NaiveSuffix(text)：在一段不可变字符串上做查询，text 属性取原文，len 取长度
- suffixes()：枚举全部后缀并整体排序，返回排序后的起始下标序列
- count_distinct_substrings()：用集合枚举全部子串去重后计数
- longest_common_prefix_of_suffixes(i, j)：逐字符比较两个后缀求公共前缀长度
- find(s)：线性扫描查找模式出现的全部起始下标
- SuffixError 是所有错误的基类，越界下标抛其子类，参数类型不对抛 TypeError

## 问题

suffixes 要先把全部后缀排一遍，子串去重更狠，先把全部子串塞进集合，
平方级的枚举加一大块内存；任意两后缀的最长公共前缀每次都要从头逐字符比；
查找是一次线性扫描。文本一长，这几条路都撑不住。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_table.py 基线一致（基线一个字不改，须全绿）
- 新行为另开测试文件，不复用朴素路径的结论替代新实现
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

（实现后补，10 行以内）
