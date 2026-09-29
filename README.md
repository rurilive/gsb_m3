# quotactl

配额发放工具，纯标准库，无外部依赖。一个上限、一个已用量，放不放得下问
一句，放得下就扣走。

## 现状

quotactl/counter.py 提供 QuotaCounter：

- QuotaCounter(limit)：一个全局上限，limit 必须是正整数，否则构造期拒绝
- check(n)：只判断 n 放不放得下，返回布尔值，不动已用量
- add(n)：把 n 记入已用量并返回累加结果；放不下抛 QuotaExceeded，已用量保持不变
- limit / used / remaining：三个只读属性，remaining 等于 limit 减 used
- 请求量为负数抛 ValueError，类型不对抛 TypeError

异常：QuotaError 为基类，超限抛 QuotaExceeded，异常对象带 requested 与 available。

没有层级，没有预留，没有借用，也没有并发保护。

## 问题

只有一个全局计数器，所有领取方挤在同一个池子里，父与子、部门与子部门之间
分不出额度，谁多拿谁少拿只能靠外部约定；领取是即时的，拿到就算消耗，没有
先占位后确认的两步，中途失败的额度退不回来；某一路额度用尽时只能干等，
不会向邻近的富余额度借；预留没有存活时间，占着不放就一直占着。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_counter.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10 及以上

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
