# flowkit

一个纯标准库的工作流状态机引擎，无外部依赖。订单、流水线、审批这类
业务一旦要按状态推进，就需要一张能承载守卫与分支的转移表，flowkit
就是干这件事的那一层。

## 现状

- `flowkit/machine.py`：`Machine(initial, states, transitions)`，注册一层
  状态与 `(source, target)` 转移。
  - `add_state(name)`：注册状态，重复或非法名在定义期报错
  - `add_transition(source, target)`：注册转移，两端须为已知状态
  - `current` / `states` / `trail` / `initial`：当前态、状态集合、推进路径
  - `targets(source=None)` / `can(target)`：从某状态可去的目标、能否一步到达
  - `step(target)`：沿转移推进并记录路径，非法转移抛 `InvalidTransition`
  - `reset()`：回到初始状态
- `flowkit/errors.py`：`FlowError` 基类与 `DefinitionError` /
  `InvalidTransition` / `TransitionConflict` 三种具体错误。

## 问题

转移只有一对起止状态，没有任何条件，谁都挡不住不该发生的推进；一台机器
只有一层状态，主流程里想嵌一段子流程就没处放；子流程退出后回不到进去前
的那个子态；同一状态出发的多条转移何时同时可用也无人校验；非法推进的
报错只有一句文案，定位不到是哪个状态出的问题。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```