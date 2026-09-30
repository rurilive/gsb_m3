# lichaotree

直线集合的在线最值工具，纯标准库，无外部依赖。

## 现状

lichaotree/lines.py 提供 NaiveLines：

- __init__(domain)：整数定义域二元组，非法即报 IllegalArgument
- add_line(k, b)：插入直线并返回插入序号，只做保存
- query_min(x) / query_max(x)：单点最小值与最大值
- query_argmin(x) / query_argmax(x)：取到最值的直线标识，并列取先
- range_min(l, r)：半开区间 [l, r) 上的最小值
- all_values(x) / lines() / domain() / __len__：读取
- 异常统一挂在 Erro 下：IllegalArgument

内部只留一个直线列表。每问一次单点最值，就把已插入的全部直线逐条
求值；每问一次区间最小值，就把区间内每个整数横坐标逐个点名、每个点
再逐条求值。没有按定义域建的树，没有中点比较，也没有区间合并。

## 问题

插入条数与查询次数一多，逐条求值就让代价按插入数乘查询数增长；
区间最小值更是把定义域里的整数点逐个点名再逐条求值，白算更多。

## 目标

见任务描述。约束：

- tests/test_naive.py 是行为基线，一个字不许改，必须原样全绿
- 新行为另开 tests/test_lichao.py，用固定输入与逐字断言
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
