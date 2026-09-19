# loglite

仓库巡检工具包：扫描 -> 核查 -> 处置 三段流水线，单进程内嵌，纯标准库，无外部依赖。

## 模块

- `loglite/manifest.py` 清单文本与条目元组互转（`name size mtime`，# 注释）
- `loglite/scanner.py` 可疑条目筛选（临时后缀 / 超大小上限），前缀 `[scanner]`
- `loglite/checker.py` 重复条目与异常 mtime 核查，前缀 `==> checker:`
- `loglite/planner.py` 问题编排成处置动作，前缀 `[planner]`

三个功能模块的过程日志已接入 `loglite/log.py` 日志层（默认兼容模式，stdout 与旧 print 逐字一致）。

## 约束

- `tests/test_pipeline.py` 锁定了返回值与 stdout 输出（含逐行文本），一个字不改
- 纯标准库，Python 3.8+

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 接入说明

- 日志层在 `loglite/log.py`：`get_logger(name)` 取 logger，用 `debug/info/warning/error` 替换裸 `print`
- 默认兼容模式：渲染不带级别与上下文装饰，接入后 stdout 与旧 print 完全一致
- `set_level(DEBUG/INFO/WARNING/ERROR)` 设全局级别，低于级别的消息不进 sink
- `set_context(k=v)` 写线程本地上下文（threading.local），每条日志自动附上；`clear_context()` 清除，线程间互不串
- `RotatingFileSink(path, max_bytes, backups)` 按大小轮转：超出即 path.1、path.2 后移，最多留 backups 个，更旧删除
- `add_sink` / `clear_sinks` / `reset` 管理输出目标；`set_compat(False)` 切结构化渲染（`LEVEL name k=v msg`）
