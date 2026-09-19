"""cfgstack: 配置分层合并。defaults < file < env，网关和三个后台任务的启动路径在用。

行为口径（历史形成的，全部要保住，tests/test_cfgstack.py 是清单）：
- 层排成显式管道，声明顺序即优先级：后声明的覆盖先声明的，同节深合并
- env 变量名形如 PREFIX__section__key，多段路径用 __ 分隔，值一律当字符串
- 缺键抛结构化 MissingKeyError（携带 key 和 source），按 kind 渲染回各调用点的历史文案，逐字依赖，别统一
"""

import json
import os


class MissingKeyError(Exception):
    """结构化缺键错误：携带 key、source 与 kind，按 kind 渲染回历史文案。

    渲染规则（历史措辞，tests 逐字锁着）：
    - require:           "missing key: {key}"
    - require_int:       "required int not found: {key}"
    - require_section:   "section '{key}' not found"
    - required_subset:   "key {key!r} missing in {source}"
    """

    def __init__(self, kind, key, source=None):
        self.kind = kind
        self.key = key
        self.source = source
        super(MissingKeyError, self).__init__(self._render(kind, key, source))

    @staticmethod
    def _render(kind, key, source):
        if kind == "require":
            return "missing key: %s" % key
        if kind == "require_int":
            return "required int not found: %s" % key
        if kind == "require_section":
            return "section '%s' not found" % key
        if kind == "required_subset":
            return "key %r missing in %s" % (key, source)
        return str(key)


class _Layer(object):
    """管道中的一层：名字 + 该层原始配置树（深拷贝，与入参隔离）。"""

    __slots__ = ("name", "data")

    def __init__(self, name, data):
        self.name = name
        self.data = data


def _deep_copy(value):
    """递归深拷贝 dict 树，非 dict 叶子原样保留。"""
    if not isinstance(value, dict):
        return value
    return {k: _deep_copy(v) for k, v in value.items()}


def merge_dicts(a, b):
    """唯一的合并函数：把 b 深合并进 a 的拷贝，返回新 dict，入参不动。

    两边同键且都是 dict 时递归合并；否则右侧覆盖左侧（dict/标量互换亦然）。
    """
    out = _deep_copy(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = merge_dicts(out[k], v)
        else:
            out[k] = _deep_copy(v)
    return out


class ConfigStack(object):
    """显式层管道。层在管道中的声明顺序即优先级：后加的覆盖先加的。"""

    def __init__(self):
        self._pipeline = []
        self._merged = {}

    def add_layer(self, name, data):
        if not isinstance(data, dict):
            raise TypeError(
                "layer %s: expected dict, got %s" % (name, type(data).__name__)
            )
        self._pipeline.append(_Layer(name, _deep_copy(data)))
        self._refresh()

    def add_file(self, name, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.add_layer(name, data)

    def apply_env(self, prefix):
        sep = prefix + "__"
        paths = {}
        for env_name in sorted(os.environ):
            if not env_name.startswith(sep):
                continue
            parts = env_name[len(sep):].split("__")
            if any(p == "" for p in parts):
                continue
            paths[".".join(parts)] = os.environ[env_name]
        env_data = {}
        for path, value in paths.items():
            cur = env_data
            parts = path.split(".")
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = value
        self._pipeline.append(_Layer("env", env_data))
        self._refresh()

    def _refresh(self):
        """按管道声明顺序，用唯一合并函数 fold 出当前有效配置树。"""
        merged = {}
        for layer in self._pipeline:
            merged = merge_dicts(merged, layer.data)
        self._merged = merged

    def layers(self):
        return [layer.name for layer in self._pipeline]

    def as_dict(self):
        return _deep_copy(self._merged)

    def _lookup(self, key):
        cur = self._merged
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return None, False
            cur = cur[part]
        return cur, True

    def get(self, key, default=None):
        v, ok = self._lookup(key)
        if not ok:
            return default
        return v

    def require(self, key):
        v, ok = self._lookup(key)
        if not ok:
            raise MissingKeyError("require", key, self.layers())
        return v

    def require_int(self, key):
        v, ok = self._lookup(key)
        if not ok:
            raise MissingKeyError("require_int", key, self.layers())
        if isinstance(v, bool):
            raise ValueError("not an int: %r" % (v,))
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                pass
        raise ValueError("not an int: %r" % (v,))

    def require_section(self, name):
        v, ok = self._lookup(name)
        if not ok or not isinstance(v, dict):
            raise MissingKeyError("require_section", name, self.layers())
        return v


def merge_profiles(base, *overrides):
    """依次叠加多个 profile，后面的赢。"""
    out = _deep_copy(base)
    for ov in overrides:
        out = merge_dicts(out, ov)
    return out


def required_subset(mapping, keys, source):
    """从 mapping 里挑出必选键。缺键按 source 报错。"""
    out = {}
    for k in keys:
        if k not in mapping:
            raise MissingKeyError("required_subset", k, source)
        out[k] = mapping[k]
    return out


def load_config(defaults, file_path, env_prefix):
    """网关用的标准入口：defaults -> file -> env 依次叠加。"""
    stack = ConfigStack()
    stack.add_layer("defaults", defaults)
    stack.add_file("file", file_path)
    stack.apply_env(env_prefix)
    return stack
