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
