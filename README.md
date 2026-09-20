# coordx

驱动一批下游参与者事务的协调者，纯标准库，无外部依赖。

## 现状

`coordx/coordinator.py` 提供 `Coordinator(participants, clock=time.monotonic)`：

- `begin()`：按注册顺序依次在各参与者上开启本地事务
- `commit()`：按同样的顺序依次提交，结束当前事务
- `participants()`：按注册顺序返回参与者名字
- `active()` / `elapsed()`：事务是否进行中、已进行的秒数（走注入时钟）
- 参与者是注入对象，约定实现 `name` 与 `begin()`/`commit()`；
  `Ledger` 是随包的内存参与者，`begin()` 之后的写入提交后才可见
- 单阶段串行推进，一步抛错就原样往上抛，协调者自己不留状态、不做补偿

## 问题

下游要求先征询"能否提交"再落定，且进程重启后不能留下半提交的账目。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_coordinator.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                           # 顺序提交演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```

## 实现说明

- 两阶段在 `coordx/twophase.py`：`TwoPhaseCoordinator(participants, store, clock, timeout)`，老 `Coordinator` 与 `tests/test_coordinator.py` 一行未动。
- 阶段一 `begin()` 后逐个 `prepare()`，全 yes 才在阶段二依次 `commit()`；反对、抛错或超时即 abort，对已征询者逆序 `rollback()`。
- 参与者需另有 `prepare()`/`rollback()`；只有 `begin()/commit()` 的老参与者不被强改，继续走老 `Coordinator`。
- `store` 注入（`MemoryStore` / 每行 JSON 且 fsync 的 `FileStore`），append 记录 begin、vote、decision、delivered、done。
- 决议先落盘再投递；重启后拿同一 store、同名同序参与者调 `recover()` 推完，已落盘结论永不翻，已投递者不重复投递。
- prepare 全过却无 decision 记录的，恢复按 abort 推：不确定就作废，在途参与者一定收到 rollback。
- 超时只认注入时钟：每个 prepare 前后各读一次时钟，差值 ≥ timeout 判超时；超时即拒绝，但原因记 `timeout`，区别于 `no` 与 `error`。
