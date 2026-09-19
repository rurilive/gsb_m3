# cfgstack

服务端配置分层合并工具：defaults < file < env，网关与若干后台任务的启动路径在用。纯标准库，无外部依赖。

## 对外 API（不可变更）

- `ConfigStack`：`add_layer(name, data)` / `add_file(name, path)` / `apply_env(prefix)` / `layers()` / `as_dict()` / `get(key, default=None)` / `require(key)` / `require_int(key)` / `require_section(name)`
- `load_config(defaults, file_path, env_prefix) -> ConfigStack`：按 defaults → file → env 依次叠加的便捷入口
- `merge_dicts(a, b)` / `merge_profiles(base, *overrides)`：深合并，返回新 dict，入参不动
- `required_subset(mapping, keys, source)`：挑出必选键，缺键抛 `MissingKeyError`
- `MissingKeyError`：缺键/缺节错误

env 变量名形如 `PREFIX__section__key`（`__` 分隔路径段），值一律当字符串，`require_int` 负责转换。层按调用先后叠加，后加的覆盖先加的；同节深合并，上层只覆盖自己给出的键。缺键报错文案以 `tests/test_cfgstack.py` 为准（各 getter 措辞不同是历史口径）。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- 层管道：`_LayerPipeline` 按声明顺序持有 `_Layer(name, data)`（入层即深拷贝），声明顺序即优先级 `defaults < file < env`；`load_config` 在一处显式声明这三层。
- 唯一合并：`merge_dicts` 是唯一深合并实现，管道 `merged()` 顺序折叠出全量树，`as_dict` 与键查询都走它；旧的四套手写合并已全部删除。
- env 层：`_parse_env` 把 `PREFIX__a__b` 收成一棵层树（值一律字符串、空路径段跳过），再作为普通层入管道，不再就地改合并树。
- 缺键错误：`MissingKeyError` 是结构化对象，携带 `key`、`source`（查过的层名元组，供下版配置来源审计）和文案模板；`_render_error` 按各调用点的历史模板渲染，异常类型与文案逐字不变。
