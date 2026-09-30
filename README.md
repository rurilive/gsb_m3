# evalx

算术表达式中缀求值与中缀转后缀工具，纯标准库，无外部依赖。

## 现状

evalx/expr.py 提供 Expression：

- evaluate(expr, variables=None)：中缀求值，支持加减乘除、括号、一元负号
- to_rpn(expr)：中缀转后缀（逆波兰）记号序列，整数原样保留，一元负号写作归类记号
- batch_evaluate(exprs, variables)：批量求值，给出结果列表与最大值对应的下标
- scan_count()：上一次操作累计的字符串扫描次数

内部只有一条路：把表达式当成字符串，按优先级从低到高反复扫描，逐段切片、
递归重建，再处理最内层括号；中缀转后缀同样靠反复扫描剥离。字符串副本随括号
层数成倍增加，一大就慢，但结果是对的。

异常基类 ExprError，派生 InvalidSyntaxError、UnbalancedParenError、
DivisionByZeroError、UnknownVariableError、EmptyExpressionError。

## 问题

现在求值、转后缀、批量求值全挤在这一条反复扫描的路上，每往里走一层括号都要把
整段字符串再扫一遍、再切一遍，括号一多扫描量成倍上去，也没有任何更省的做法可用；
中缀转后缀同样只有反复剥离一条路；表达式里的变量只有求值一条道，转后缀完全接不
上；错误口径虽然集中，但缺少一个能打印的规模数字去说明反复扫描到底多花了多少。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_expr.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
