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

- 层是显式管道：`ConfigStack._pipeline` 按 `add_layer`/`add_file`/`apply_env` 的调用顺序存层，声明顺序即优先级（后声明覆盖先声明）。
- 每层保存独立深拷贝的原始数据；`_refresh()` 按管道顺序从空 dict 起逐层 fold，结果即有效配置树。
- 合并只有一个函数 `merge_dicts(a, b)`：栈合并、`as_dict` 的拷贝路径、`merge_profiles` 全部走它，规则为同键双 dict 递归、否则右侧覆盖。
- 缺键统一抛结构化 `MissingKeyError(kind, key, source)`：栈类 getter 的 source 是已声明层名列表，`required_subset` 的 source 是传入的来源名。
- 异常在构造时按 kind 渲染回四处历史文案（`missing key:` / `required int not found:` / `section … not found` / `key … missing in …`），类型与文本逐字不变。
