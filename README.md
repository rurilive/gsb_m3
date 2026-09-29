# quory

副本共识读写库：纯标准库，无外部依赖，副本与网络以可注入的模拟对象表达，
使读写时序完全可复现。

## 现状

quory/writer.py 提供 WriteAll，一个向全部副本广播写的写入器：

- WriteAll(replicas)：持有一组外部注入的副本对象
- put(key, value)：向每个副本依次 set，任一失败即整体失败
- get(key)：按副本顺序问一遍，取第一个非空回答
- replicas_ok()：所有副本都可用时返回真
- 副本只需实现 set(key, value) 与 get(key)，键不存在时 get 返回 None

当前写要求所有副本都成功，一个副本慢就整体阻塞，没有法定人数，没有读修复，
也没有版本与时间戳。

## 目标（见任务描述）

约束：

- 现有行为与 tests/test_writer.py 基线一致，基线文件一个字不改
- 新行为另开 tests/test_quorum.py
- 纯标准库，异常继承 QuorumError 基类

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
