# btreex

有序映射，纯标准库，无外部依赖。

## 现状

`btreex/store.py` 提供 `FlatMap`，一个把全部键值塞在平铺数组里的有序映射：
一个按键升序维护的键列表，配一条平行的取值列表。

- `put(key, val)`：插入或覆盖，新键返回 True、覆盖返回 False
- `get(key, default=None)`：二分查找取值
- `delete(key)`：线性删除，删到返回 True、不存在返回 False
- `keys_in_range(lo, hi)`：闭区间 `[lo, hi]` 的键值对，按键升序
- `size()` / `keys()` / `items()` / `__len__` / `__contains__`
- 越界区间（lo 大于 hi）与非法键（非整数非字符串）报 ValueError

插入线性找位后把后半段整体后移，删除线性定位后把后半段整体前移。没有任何树
结构，没有节点，没有分裂合并，规模一大每次增删都要搬动一大段。

## 问题

数据量增长后，插入与删除的搬移代价随规模线性上升，最坏情况下一次改动就要挪动
几乎整个数组，利用率与可扩展性都不理想。

## 目标

见任务描述。约束：

- 基线行为与 `tests/test_store.py` 保持一致（基线一字不改，必须全绿）
- 新行为另开 `tests/test_btree.py`，纯标准库，全部能力仍在 `btreex` 包内
- `demo.py` 第二段补一轮演示，README 末尾补实现说明

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
