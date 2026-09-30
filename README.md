# stablematch

稳定婚姻配对库，纯标准库，无外部依赖。

## 现状

`stablematch/core.py` 提供一组函数，两拨人一拨男方一拨女方，各给一份对另一侧
的偏好次序：

- `normalise(men, women, men_prefs, women_prefs)`：校验两侧名单与偏好表，把没
  提到的人按姓名升序补在偏好后面，返回整理好的四元组；输入不合法抛 `InvalidInput`
- `enumerate_pairings(men, women)`：穷举两侧之间所有配对方案，逐条返回配对字典
- `instabilities(pairing, men_prefs, women_prefs)`：列出方案里所有互相更中意的
  一男一女，`first_unstable` 只取第一条，没有则返回 None
- `all_stable(men, women, men_prefs, women_prefs)`：把全部稳定方案挑出来，按男方
  名次向量升序返回
- `stable_pairing(...)`：返回对男方最有利的那个稳定配对，一个都没有时抛
  `UnstableMatching`
- 异常都继承 `Erro` 基类

## 问题

现在的实现只能穷举：方案数随人数阶乘增长，六男六女就是七十多万条待判，人数
再多直接跑不动。而且只有这一条路径，规模稍大就没有可用的结果，也拿不到另一
套口径交叉核对。

## 目标

见任务描述。约束：

- `tests/test_baseline.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```
（实现后补，10 行以内）
