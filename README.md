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
- `rollback(obj_id, version)`：把当前版本指回链上已有的某一版
- `delete(obj_id, version)`：从链上删掉某一版，返回是否真的删掉

`_Node` 是链上的节点，同时持有 `prev` / `next` 两个方向的指针；
`_nodes` 按版本号索引节点，`_head` / `_tail` 记住两端。

## 问题

线上反馈：并发写同一对象时版本号会重复，同一个毫秒里提交的版本顺序会漂移，
回滚之后再写新版本会踩掉历史上的旧版本，删掉中间某一版之后比它旧的版本
全都读不出来。细节见任务描述。

## 目标

修好 `snapline/chain.py`，保证下面四条不变量：

- 版本号严格单调递增
- 同一时刻提交的版本按提交先后稳定排序
- 回滚后再写，新版本号不回退，不覆盖历史
- 删除中间版本后链仍然完整，剩下的每一版都还能回读

约束：

- 纯标准库，不引三方依赖
- `tests/test_chain.py` 是行为基线，一个字不改，必须原样全绿

## 运行

```bash
python3 demo.py                          # 四类顺序错乱现象的复现
python3 -m unittest discover -s tests -v # 行为基线测试
```
