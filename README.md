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

- `TwoPhaseCoordinator(participants, store, clock=time.monotonic, prepare_timeout=5.0)`：`begin()` 后 `prepare()` 逐个征询，全票赞成才落 `committing` 决议并 `commit()`；反对/抛错/超时落 `aborting` 决议，按相反顺序对已 prepare 者 `rollback()`。
- 意图与决议经注入的 `TransactionStore` 落盘（`MemoryStore` 测试用，`JsonFileStore` 原子替换文件）；每次征询先落 `asking`、赞成票和每个参与者的裁决送达（`done`）都逐条 fsync。
- 重启后拿同一 store、同一批参与者调 `recover()`：决议前崩溃的事务只能 abort；已落盘的 commit/abort 结论只重放、永不翻转，prepare 成功却没等到裁决的参与者一定会收到结论。
- 超时口径：协调者在每次 `prepare()` 前后各读一次注入时钟，读数之差严格大于 `prepare_timeout` 即超时；超时按拒绝处理，但记录的原因是 `timeout`（`abort_reason()`/落盘字段），区别于反对 `veto` 与抛错 `error`。
- 老参与者只有 `begin()`/`commit()` 即可继续服务单阶段 `Coordinator`，两阶段才需要 `prepare()`/`rollback()`（见 `PrepareParticipant`/`TwoPhaseLedger`）。
