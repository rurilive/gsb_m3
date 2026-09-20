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

## 测试

```bash
python3 -m unittest discover -s tests
```

## Known Issues

以下问题均已修复（修复代码见 `depsolve/resolver.py`，回归测试见 `tests/test_regressions.py`）。

1. **自依赖不报循环依赖**
   根因：DFS 收集闭包时（`_visit`）对 `dep == name` 做了显式 `continue` 跳过，
   自环永远到不了 `_visiting` 路径栈的环检测。已删除该特判，自依赖现在与普通环一样
   抛 `CircularDependencyError`，环路径形如 `pkg -> pkg`。
2. **同一清单两次解析、构建顺序不一致，缓存反复失效**
   根因：入口遍历使用 `set(requests)`，集合迭代顺序受 `PYTHONHASHSEED` 影响，
   进而改变 DFS 后序（`_order`）。已改为 `dict.fromkeys(requests)`：按请求给定顺序
   遍历并去重，同输入（含 `enabled`）的输出逐项一致。
3. **未启用的可选加速组仍被解析、甚至报循环依赖**
   根因：`_direct_deps` 中用了 `deps.extend(enabled or optional)`——当没有任何可选项
   被启用时 `enabled` 为空列表（假值），`or` 回退成把整组可选依赖全部加入图，
   于是未启用的组也成环。已改为只 `extend(enabled)`，未启用的可选依赖完全不进图；
   显式启用后若成环，仍正常抛 `CircularDependencyError`。
4. **`json>=2.0` 与 `json<2.0` 冲突未报错，静默锁到 `json@1.1.0`**
   根因：`_select_version` 对每条约束**独立**扫描版本并覆盖 `best`，最终只保留
   “最后一条约束能接受的某个版本”，从不要求同一版本同时满足全部约束。
   已改为先筛出同时满足所有约束的候选版本再取最高；候选为空时抛 `ConflictError`，
   错误信息带每条约束及其来源包。
