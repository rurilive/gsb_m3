# loglite

仓库巡检工具包：扫描 -> 核查 -> 处置 三段流水线，单进程内嵌，纯标准库，无外部依赖。

## 模块

- `loglite/manifest.py` 清单文本与条目元组互转（`name size mtime`，# 注释）
- `loglite/scanner.py` 可疑条目筛选（临时后缀 / 超大小上限），前缀 `[scanner]`
- `loglite/checker.py` 重复条目与异常 mtime 核查，前缀 `==> checker:`
- `loglite/planner.py` 问题编排成处置动作，前缀 `[planner]`
- `loglite/logging.py` 结构化日志层：级别过滤、线程上下文、可轮转文件 sink

## 约束

- `tests/test_pipeline.py` 锁定了返回值与 stdout 输出（含逐行文本），一个字不改
- 纯标准库，Python 3.8+

## 运行

```bash
python3 demo.py                          # 现状 + 结构化日志演示
python3 -m unittest discover -s tests -v # 行为基线 + 日志层测试
```

## 接入说明

- `get_logger("name")` 取日志器，默认前缀 `[name] `；checker 用自定义前缀 `==> checker: `
- 默认配置即兼容模式：`plain` 渲染写 stdout，输出与旧 `print` 逐字一致，`redirect_stdout` 照常捕获
- `set_level("DEBUG"|"INFO"|"WARNING"|"ERROR")` 设全局级别，低于级别的记录不进任何 sink
- `set_context(run="x")` 的字段经 `threading.local` 自动附到当前线程每条日志，`clear_context()` 清除
- `add_sink(FileSink(path, max_bytes=1e6, backups=5, render="json"))` 按大小轮转为 `path.1`、`path.2`，超出 backups 的旧文件删除
- 渲染器可选 `"plain"`（兼容）/`"text"`（带级别与 `[k=v]` 上下文）/`"json"`，`StreamSink`、`CaptureSink` 同理
- `add_sink` / `remove_sink` / `clear_sinks` 管理 sink，`reset()` 恢复默认（测试隔离用）
