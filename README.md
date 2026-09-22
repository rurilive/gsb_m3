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

## 实现说明

- 删除用哨兵 `DELETED` 表示：`append(obj, field, DELETED, v)`；`at` 重建快照时该字段不出现，`history` 仍保留全程
- `merge(log, obj, branches, resolve=None, start_version=1)`：`branches` 为 `[(分支名, [Change...])]`，胜出的变更以 `start_version` 起递增版本号 append 进 `log`
- 默认策略 `last_write_wins`：删除标记优先；否则版本高者胜，并列取 branches 里靠后的分支
- 自定义消解函数签名：`resolve(field, options) -> Option`，`options` 是各分支候选 `Option(source, change)`，须返回其中之一
- 来源口径：`MergeResult.entries` 每条是 `MergedEntry(change, source)`，标明该条来自哪条分支
- 冲突口径：每次冲突记 `Conflict(field, winner, losers)`，被消解的输家可经 `MergeResult.losers` 一并取出
- `MergeResult.snapshot()` 折叠合并结果，被删字段不出现；与合并后 `log.at(obj, 最新版本)` 一致

## 问题

两份改动从同一版本分叉之后没法合回一条线：同字段撞车没有消解口径，合并完也说不清每条变更打哪儿来。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_changelog.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                            # 单线变更与快照重建演示
python3 -m unittest discover -s tests -v   # 行为基线测试
```
