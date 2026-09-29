# dagsched

批处理编排用的任务依赖 DAG 调度器，纯标准库，无外部依赖。

## 现状

`dagsched/scheduler.py` 提供 `Scheduler`：

- `add_task(name)`：登记任务节点，重复登记不改动已有依赖
- `add_dependency(task, dep)`：声明 `dep -> task` 的依赖边，重复或成环抛 `CycleError`
- `topo_order()`：Kahn 拓扑排序，无前驱节点按任务名字典序出队，结果确定
- `detect_cycle()`：有环返回环上任务名，无环返回 None
- `ready_tasks(done=None)`：依赖已满足且不在 done 中的任务名
- `predecessors(name)` / `successors(name)`：直接前驱与直接后继
- `has_task(name)` / `tasks()`：登记查询

任务名非空字符串校验、未知任务抛 `UnknownTask`、依赖缺失抛 `DependencyNotFound`，内部一把可重入锁保护读写。

## 问题

现有实现只能给出一个串行的拓扑序：没有并行层级概念，环只给一个不带诊断的坏图，任务只能在建图期一次加完，同层之间无序，失败后下游仍会被判为就绪。

## 目标

见任务描述。约束：

- `tests/test_scheduler.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 拓扑排序与就绪任务演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
