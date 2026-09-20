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
`_nodes` 按版本号索引节点，`_head` / `_tail` 记住物理链两端，
`_cursor` 是 rollback 挪动的当前版本游标，`_issued` 记住每对象发过的
最大版本号（发号高水位）。

## 保证的不变量

`snapline/chain.py` 修复后保证：

- 版本号严格单调递增：发号与挂链在同一把锁内，并发写不重号；号取自
  每对象的高水位 `_issued + 1`，与游标无关
- 同一毫秒（乃至时钟抖动）提交的版本按提交先后稳定排列：`history()`
  直接沿物理链 `tail -> head` 走，不用时间戳排序
- 回滚后再写，新版本号不回退、不覆盖历史：rollback 只移动游标，
  不动高水位，回滚后下一个版本号仍是历史最大号 + 1
- 删除中间版本后链仍然完整：delete 双向摘链并缝合两侧，剩下的每一版
  都能回读，从任意一版沿 `prev` / `next` 都能一路走到两端，不重不漏

约束：

- 纯标准库，不引三方依赖
- `tests/test_chain.py` 是行为基线，一个字不改，必须原样全绿

## 运行

```bash
python3 demo.py                          # 四类场景复现与不变量校验（全 [OK]）
python3 -m unittest discover -s tests -v # 行为基线测试
```
