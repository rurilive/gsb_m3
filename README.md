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

- 删除用哨兵 `DELETED` 表示：`append(obj, field, DELETED, v)`；`at` 遇到它把该字段从快照摘掉，之后再有普通变更则重新出现。
- `merge(obj, branches, strategy="latest", clock=...)`：`branches` 为 `{分支名: ChangeLog}`（各含分叉后的变更），返回 `MergeResult`。
- 默认策略 `latest`：删除优先，否则版本高者胜，并列取分支名大者；另有 `first`（先写优先）可换。
- 自定义消解：传函数 `resolver(field, candidates) -> candidate`，`candidates` 是 `Candidate(change, source)` 列表，须返回其中之一。
- 来源：`result.entries` 每条都带 `source`；`result.source_of(change)` 反查合并日志里任意一条来自哪条分支。
- 冲突：同字段值有分歧才记账，`result.conflicts` 收 `Conflict(field, winner, losers)`；输家仍留在合并日志里，`history` 可见、快照不生效。

## 运行

```bash
python3 demo.py                            # 单线变更 + 多分支合并演示
python3 -m unittest discover -s tests -v   # 行为基线 + 合并测试
```
