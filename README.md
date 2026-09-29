# exprkit

一个纯标准库的算术表达式求值器，无外部依赖。配置、公式与规则引擎里经常要
让用户写一小段表达式，再由程序算出一个数，exprkit 就是干这件事的那一层。

## 现状

- `exprkit/tokens.py`：`Token(kind, text, value, start, end)`，只记 src 上的
  字符下标区间，尚未把下标换算成行列号。
- `exprkit/lexer.py`：`tokenize(src)` 把原文切成 token，运算符最长匹配优先，
  `OPERATORS` 里含 `**`、`==`、`<=`、`&&` 等尚未接入语法的多字符运算符。
- `exprkit/parser.py`：`parse(src)` 是递归下降解析器，只覆盖加减、乘除取模、
  一元正负与括号，末尾残留 token（如 `1 2`）一律报错。
- `exprkit/eval.py`：`eval(src)` 每次调用都重新分词、重新解析再求值，不缓存
  语法树，相同表达式重复求值每次都从头再编一遍。
- `exprkit/errors.py`：`ParseError` 与 `EvalRuntimeError` 带出错表达式与字符
  下标，`line` 与 `col` 当前一律按第一行算。

## 问题

表达式里不能写变量，一切值都得硬编在原文里；没有比较与逻辑，判断走不到；
除零或残缺表达式的诊断只有字符下标，长表达式里不好定位到第几行第几列；
每次求值都重解析，同一段表达式在热路径上反复用会白白重复编译。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
