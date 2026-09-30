# polyhash

多项式哈希字符串池，纯标准库，无外部依赖。

## 现状

`polyhash/core.py` 提供 `StringPool`：

- `add(text)`：登记一段字符串，返回它的下标，下标即插入顺序
- `size()` / `get(index)`：串池大小、按下标取回副本
- `equal(left, right)`：逐字符判断两串是否相等
- `lcp(left, right)`：逐字符求两串最长公共前缀长度
- `duplicates()`：找出全部相重串，返回按下标升序排好的分组
- `access_count` / `reset_access_count()`：字符位置比较次数，可归零

`build_text(seed, length)` 用固定线性同余序列拼出确定性小写文本，供演示与测试构造可复现输入。

## 问题

判等、前缀与查重全部靠逐字符比较糊出来：每比较一对串都要从第一个字符走起，
访问计数随串长与查询次数线性增长。没有滚动哈希，没有前缀哈希与取模幂，
也没有多重基数防碰撞的意识，长串批量查询时代价高得离谱。

## 目标

把 `core.py` 扩成以滚动哈希为主路径、并保留独立逐字符口径交叉核对的形态，见任务描述。约束：

- 现有行为与 `tests/test_core.py` 基线保持一致（基线一个字不改）
- 纯标准库，Python 3.10+
- 新老两条路径对同一批固定输入逐项一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
