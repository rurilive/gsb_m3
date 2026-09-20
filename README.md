# loglite

仓库巡检工具包：扫描 -> 核查 -> 处置 三段流水线，单进程内嵌，纯标准库，无外部依赖。

## 模块

- `loglite/manifest.py` 清单文本与条目元组互转（`name size mtime`，# 注释）
- `loglite/scanner.py` 可疑条目筛选（临时后缀 / 超大小上限），前缀 `[scanner]`
- `loglite/checker.py` 重复条目与异常 mtime 核查，前缀 `==> checker:`
- `loglite/planner.py` 问题编排成处置动作，前缀 `[planner]`
- `loglite/log.py` 结构化日志层：级别过滤、线程本地上下文、大小轮转文件 sink

三个功能模块的过程日志已接入日志层，默认兼容模式下 stdout 与旧 print 逐字节一致。

## 约束

- `tests/test_pipeline.py` 锁定了返回值与 stdout 输出（含逐行文本），一个字不改
- 纯标准库，Python 3.8+

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 接入说明

- `log.get_logger(name)` 取 logger，用 `debug/info/warning/error` 记录
- `log.set_level(log.WARNING)` 全局过滤，低于级别的消息不进任何 sink
- `log.set_context(k=v)` 写线程本地上下文，每条日志自动附上；`log.clear_context()` 清除
- sink：`log.StreamSink(stream, compat=)` 写流；`log.RotatingFileSink(path, max_bytes, backups)` 按大小轮转
- `compat=True` 渲染与旧 print 一致；默认即兼容 stdout sink，接入后 stdout 不变
- 自定义配置后用 `log.reset()` 可恢复默认（测试 tearDown 里建议调用）
