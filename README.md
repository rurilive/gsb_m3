# loglite

仓库巡检工具包：扫描 -> 核查 -> 处置 三段流水线，单进程内嵌，纯标准库，无外部依赖。

## 模块

- `loglite/manifest.py` 清单文本与条目元组互转（`name size mtime`，# 注释）
- `loglite/scanner.py` 可疑条目筛选（临时后缀 / 超大小上限），前缀 `[scanner]`
- `loglite/checker.py` 重复条目与异常 mtime 核查，前缀 `==> checker:`
- `loglite/planner.py` 问题编排成处置动作，前缀 `[planner]`

三个功能模块的过程日志已接入 `loglite/log.py` 日志层，兼容模式下输出与旧 `print` 逐字一致。

## 约束

- `tests/test_pipeline.py` 锁定了返回值与 stdout 输出（含逐行文本），一个字不改
- 纯标准库，Python 3.8+

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 接入说明

- 日志层在 `loglite/log.py`：`get_logger(name, compat_prefix=...)` 替换裸 `print`
- 默认兼容模式：渲染仅「前缀 + 消息」，stdout 与旧 `print` 逐字一致
- `set_structured(True)` 后输出 `LEVEL [name] msg k=v`，供统一采集解析
- `set_level("DEBUG"/"INFO"/"WARNING"/"ERROR")` 全局过滤，低于级别不进 sink
- `set_context(**kv)` / `clear_context()` 管理线程本地上下文字段，线程间互不串
- `add_sink(RotatingFileSink(path, max_bytes, backups))` 按大小轮转：`path.1`、`path.2` 后移，超出 `backups` 的删除
- `reset_sinks()` 恢复默认 stdout sink
