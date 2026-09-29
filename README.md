# bloomx

成员集合工具包，纯标准库，无外部依赖。

## 现状

`bloomx/member.py` 提供 `ExactSet`，用 Python 内置 set 精确保存元素：

- `add(item)`：加入一个元素，重复加入幂等
- `contains(item)`：成员判断，精确无误差
- `size()` / `len()`：当前元素个数

语义上加入过的元素一定判为存在，没加入过的一定判为不存在，代价是内存随元素数量线性增长，没有位数组、没有哈希函数、也没有误判的概念。

## 目标（见任务描述）

把 bloomx 从精确集合扩成概率成员集合，详见任务描述。

## 运行

```bash
python3 demo.py                          # 精确集合的存在性判断演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

（实现后补，10 行以内）
