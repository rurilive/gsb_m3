# pseg

可版本化计数工具，纯标准库，无外部依赖。

## 现状

`pseg/pst.py` 提供 `FlatCtl`：

- `add(i, delta)`：对下标 i 加增量，返回新数组的一份拷贝
- `point(i, version=None)`：取下标 i 的当前取值或某个历史版本的取值
- `snapshot()`：把当前整份数组存为一个版本，返回版本号
- `count_le(x)`：统计取值不大于 x 的位置个数（线性扫描）
- `kth_ge(x)`：返回第一个取值不小于 x 的下标（线性扫描）
- `size` / `max_value` / `values()` / `version_count()` / `__len__`：读取结构

内部只是一个计数数组。每次更新都对整份数组拷贝一份，每个版本也是把
当时的整份数组原样存下来。更新与快照的代价都随位置数线性增长，
版本一多内存就线性膨胀。非法下标抛 `PstIndexError`，它继承自基类 `PstError`。

## 问题

整体拷贝使得单次更新与单次快照的代价都随位置数线性增长，
历史版本之间没有任何共享，查询也只能线性扫描，
值域一大、版本一多，内存与时间都撑不住。

## 目标

见任务描述。约束：

- `tests/test_pst.py` 是行为基线，一个字不许改，必须原样全绿
- 新行为另开 `tests/test_persistent_seg.py`，用固定序列与逐字断言
- 纯标准库
- 新异常统一继承 `PstError`

## 运行

```bash
python3 demo.py                                 # 可版本化计数现状演示
python3 -m unittest discover -s tests           # 行为基线测试
```

（实现后补，10 行以内）
