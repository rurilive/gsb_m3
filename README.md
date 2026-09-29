# boundedq

有界多生产者多消费者队列，纯标准库，无外部依赖。

## 现状

boundedq/queue.py 提供 FifoQueue：

- push(item)：把元素放到队尾，返回元素本身；元素为 None 抛 ValueError
- pop()：从队首取出一个元素，队列为空返回 None
- peek()：看一眼队首元素但不取走，队列为空返回 None
- len() / bool()：队列长度与是否非空

底层是一把互斥锁加一个双端队列。队列无界，放多少存多少；取不到就返回 None，
不阻塞、不排队、不认时钟，也没有容量、批量与关闭之类的语义。
tests/test_fifo.py 锁住这些行为。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_fifo.py 基线一致（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）