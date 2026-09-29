# jobrig

带依赖、优先级、抢占与取消的工作队列任务编排队列，纯标准库，无外部依赖。

## 现状

jobrig/queue.py 提供 FifoQueue：

- push(task)：把任务放到队尾，返回任务本身；任务为 None 抛 ValueError
- pop()：从队首取出一个任务，队列为空返回 None
- peek()：看一眼队首任务但不取走，队列为空返回 None
- len() / bool()：队列长度与是否非空

任务体不做任何校验或变换，入队是什么、出队还是什么，没有依赖、没有优先级、
没有抢占，也没有取消。tests/test_queue.py 锁住这些行为。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_queue.py 基线一致（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）