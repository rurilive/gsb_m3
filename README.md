# persist

可持久化数组，纯标准库，无外部依赖。工程里常要在同一个数组上不断改一点、
又想回查任意历史版本，persist 就是负责这件事的那一层。

## 现状

persist/parray.py 目前是最朴素的一层实现：

- PersistentArray(length, fill)：建初始空版本，编号为零，每个位置取填充值
- modify(version, index, value)：单点修改，返回新版本号
- query(version, index)：查某个版本的某个位置
- snapshot(version)：取出某个版本的整份数组快照
- kth(lo, hi, k)：版本区间内各次修改写入值的第 k 小
- 全部异常继承 Erro 基类，再分 BadArgument、VersionOutOfRange、
  IndexOutOfRange、KthOutOfRange 几个子类

现有实现每次单点修改都把整份数组拷一份存成新版本，历史查询按键取对应整份快照。
结果对，但规模一大每次修改都要线性拷贝，版本一多内存就平方增长；也没有一条按
版本号与下标走链式复用的做法可以拿来逐项对照。

## 问题

把现有这套整份拷贝扩成可持久化线段树，缺的东西集中在几处：单点修改没有只新建
从根到叶的一条链、其余节点复用旧版本；没有按版本号与下标查任意历史版本某个位置
的做法；也没有版本区间第 k 小的加速；另起一条独立朴素路径逐项一致的对照还没有。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_baseline.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+
- 结果确定性，固定输入重复跑新老两条路径逐项一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
