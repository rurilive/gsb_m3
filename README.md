# depsolve

构建系统的依赖解析模块：读入包清单，解析闭包、择优版本、按拓扑序输出构建顺序。

## 清单格式

```python
MANIFEST[name] = {
    "versions": ["1.0.0", "1.2.0"],   # 可用版本，升序列出
    "depends": ["fmt>=1.0", "json"],  # 硬依赖，可带版本约束
    "optional_depends": ["accel"],    # 可选依赖组，默认不参与解析
}
```

## 解析语义

- `resolve(manifest, requests, enabled=None)` 返回拓扑序的 `"name@version"` 列表，被依赖者在前
- 同一包被多方依赖时，必须同时满足全部版本约束，取满足约束的最高版本；没有任何版本同时满足时抛 `ConflictError`
- 可选依赖仅在 `enabled` 集合中显式启用时才进入依赖图，未启用时完全不参与解析
- 依赖图中出现环（包括包依赖自己）时抛 `CircularDependencyError`，错误信息带环路径
- 依赖了清单中不存在的包时抛 `UnknownPackageError`
- 解析是确定的：同一输入（含 `enabled`）两次解析，输出逐项一致

## 运行

```bash
python3 demo.py
```

## Known Issues

以下缺陷已于本轮修复，回归测试见 `tests/`（`python3 -m unittest discover -s tests`）：

- **自依赖清单不报错**：`_visit` 中对 `dep == name` 做了静默跳过，自依赖从未进入环检测。
  现已移除该特判，包依赖自己（含带版本约束的写法）会正常抛出 `CircularDependencyError`。
- **同一清单两次解析顺序不一致**：`resolve` 用 `set(requests)` 迭代入口包，字符串 set 的
  迭代顺序受 `PYTHONHASHSEED` 影响，每次进程启动都可能不同，导致拓扑序不稳定、缓存失效。
  现改为按 `requests` 原始顺序去重遍历，输出完全确定。
- **未启用的可选依赖组参与解析**：`_direct_deps` 中 `deps.extend(enabled or optional)` 在
  没有命中任何启用项时退化为把整组可选依赖全部加入依赖图，可选组内部的环（如
  `archive-sse` 反向依赖 `archive`）被误报为循环依赖。现改为仅加入 `enabled` 显式启用的项。
- **版本约束冲突不报错**：`_select_version` 逐条约束循环覆盖 `best`，实际只生效最后一条
  约束（如 `json>=2.0` 与 `json<2.0` 并存时悄悄锁了 `json@1.1.0`）。现改为取所有约束的
  交集，没有任何版本同时满足时抛 `ConflictError`，错误信息列出各需求方的约束。
- **请求的入口包不在清单中时抛 `KeyError`**：`_visit` 入口未校验根包是否存在，现统一抛
  `UnknownPackageError`。
