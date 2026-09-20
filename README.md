# snapline

配置对象的历史快照链，纯标准库，无外部依赖。每个对象一条独立的链，
版本号从 1 开始，时间来自注入的 clock。

## 现状

`snapline/chain.py` 提供 `SnapLine`：

- `SnapLine(clock=time.monotonic)`：clock 返回当前时刻，测试可注入
- `snapshot(obj_id, state)`：记一版快照，返回分配到的版本号
- `at(obj_id, version)`：回读指定版本的状态，版本不存在返回 None
- `latest(obj_id)`：返回当前版本 `(version, state)`，对象不存在返回 None
- `history(obj_id)`：列出该对象全部版本号，旧的在前
- `ancestors(obj_id, version)`：从指定版本沿 `prev` 一路回走到最早一版，返回版本号列表
- `rollback(obj_id, version)`：把当前版本指回链上已有的某一版
- `delete(obj_id, version)`：从链上删掉某一版，返回是否真的删掉

`_Node` 是链上的节点，同时持有 `prev` / `next` 两个方向的指针；
`_nodes` 按版本号索引节点，`_head` / `_tail` 记住现存两端，节点之间
用 `prev` / `next` 双向链接，删除时两边指针一起补，回遍历可以直接
跨过被删掉的缺口。

## 不变量

`snapline/chain.py` 保证下面几条：

- 版本号严格单调递增：序号和版本号都在同一把锁内分配，并发提交不会重号
- 同一时刻提交的版本按提交先后稳定排序：排序键是 `(时刻, 全局提交序号)`
- 回滚只挪动当前游标；之后再写，版本号从“历史上发过的最大值 +1”开始，
  不回退、不覆盖历史
- 删除任意一版后链仍然完整，剩下的每一版都能回读；从任意现存版本用
  `ancestors()` 往回遍历都能一路走到底、不重不漏

约束：

- 纯标准库，不引三方依赖
- `tests/test_chain.py` 是行为基线，一个字不改，必须原样全绿

## 运行

```bash
python3 demo.py                          # 四类顺序错乱现象的复现
python3 -m unittest discover -s tests -v # 行为基线测试
```
