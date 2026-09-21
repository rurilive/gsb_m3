# changelogd

对象的字段变更日志：按版本号记下每次改动，随时重建历史快照。纯标准库，无外部依赖、无真实 IO。

## 现状

`changelogd/changelog.py` 提供 `ChangeLog`：

- `ChangeLog(clock=time.time)`：clock 为注入时钟，每条变更的 ts 取自它
- `append(obj, field, value, version)`：追加一条变更，返回该记录（`obj` / `field` / `value` / `version` / `ts`）
- `history(obj)`：该对象的全部变更，按 append 顺序，返回新列表
- `at(obj, version)`：重建快照——每个字段取 append 顺序里最后一条 `version` 不超过给定值的变更
- `objects()`：出现过的对象名，按首次 append 顺序

目前只有一条时间线，`version` 由调用方给，本包不校验它是否单调。

## 问题

两份改动从同一版本分叉之后没法合回一条线：同字段撞车没有消解口径，合并完也说不清每条变更打哪儿来。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_changelog.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 实现说明

- 合并入口 `merge(obj, branches, base_version, into=None, resolver=None, clock=...)`：`branches` 为 `{分支名: ChangeLog}`，只收各分支 `version > base_version` 的变更；`into` 缺省时新建日志并先抄入基线变更
- 删除：`append(obj, field, DELETED, version)` 记墓碑，`at` 重建快照时该字段不再出现，`history` 仍能看到删除全过程
- 默认策略 `last_write_wins`：删除优先，否则版本号大者胜，平手取分支顺序靠后者；可换成 `first_write_wins` 或自定函数
- 消解函数签名：`resolver(field, candidates) -> Candidate`，`candidates` 是各分支对该字段的最终 `Candidate(origin, change)`，必须返回其中之一
- 来源记账：`MergeResult.changes` 是 `MergedChange(change, origin)` 列表，每条合并变更都标了来自哪条分支
- 冲突记账：`MergeResult.conflicts` 是 `Conflict(field, winner, losers)` 列表，被消解掉的输家全在 `losers` 里；双方同值不算冲突

## 运行

```bash
python3 demo.py                            # 单线变更、快照重建与多分支合并演示
python3 -m unittest discover -s tests -v   # 行为基线测试
```
