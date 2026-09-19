"""cfgstack: 配置分层合并。defaults < file < env，网关和三个后台任务的启动路径在用。

行为口径（历史形成的，全部要保住，tests/test_cfgstack.py 是清单）：
- 层合并是深合并：上层只覆盖自己给出的键，同节其他键保留
- env 变量名形如 PREFIX__section__key，多段路径用 __ 分隔，值一律当字符串
- 各 require_* 缺键时的报错文案是各自的历史措辞，逐字依赖，别统一
"""

import json
import os


class MissingKeyError(Exception):
    """配置缺键（结构化错误对象）。

    携带 key（缺的键）、source（查过的来源：栈侧是管道各层名，
    required_subset 侧是调用方给的 source 字符串）与渲染模板；
    最终文案由 _render_error 按模板渲染，历史措辞逐字不变。
    """

    def __init__(self, key, source, template):
        self.key = key
        self.source = source
        self.template = template
        super().__init__(_render_error(template, key, source))


# 缺键错误的历史文案模板（% 风格，逐字锁定，不要统一措辞）。
_ERR_MISSING = "missing key: %s"
_ERR_INT = "required int not found: %s"
_ERR_SECTION = "section '%s' not found"
_ERR_SUBSET = "key %r missing in %s"


def _render_error(template, key, source):
    """把结构化缺键错误渲染回历史文案。"""
    if template is _ERR_SUBSET:
        return template % (key, source)
    return template % key


def merge_dicts(a, b):
    """深合并两个 dict，返回新 dict，入参不动。dict 对 dict 递归，否则后者覆盖。

    cfgstack 唯一的合并实现：层管道叠加、入层拷贝、as_dict 都收敛到这里。
    """
    out = {}
    for k, v in a.items():
        out[k] = _copy_node(v)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = merge_dicts(out[k], v)
        else:
            out[k] = _copy_node(v)
    return out


def _copy_node(v):
    """深拷贝 dict 子树；非 dict（叶子/列表等）按原样引用。"""
    if isinstance(v, dict):
        return merge_dicts(v, {})
    return v


def merge_profiles(base, *overrides):
    """依次叠加多个 profile，后面的赢。"""
    out = base
    for ov in overrides:
        out = merge_dicts(out, ov)
    return out


def _walk_set(data, path, value):
    """按 dotted path 写入嵌套 dict，中间层缺就建。"""
    parts = path.split(".")
    cur = data
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def _parse_env(prefix):
    """把 PREFIX__a__b 形式的环境变量收成一棵层树；值一律保持字符串。

    空路径段 / 裸前缀跳过（历史口径）。同名变量按名字排序后写入，
    与旧实现逐一遍历 os.environ（sorted）的结果一致。
    """
    sep = prefix + "__"
    tree = {}
    for env_name in sorted(os.environ):
        if not env_name.startswith(sep):
            continue
        parts = env_name[len(sep):].split("__")
        if any(p == "" for p in parts):
            continue
        _walk_set(tree, ".".join(parts), os.environ[env_name])
    return tree


class _Layer(object):
    """管道中的一层：名字 + 该层独立持有的配置树副本。"""

    def __init__(self, name, data):
        self.name = name
        self.data = merge_dicts(data, {})


class _LayerPipeline(object):
    """显式层管道：声明顺序即优先级（低 -> 高），后声明的层覆盖先声明的。

    合并只在 merged() 一处经 merge_dicts 顺序折叠完成。
    """

    def __init__(self):
        self._layers = []

    def append(self, name, data):
        self._layers.append(_Layer(name, data))

    def names(self):
        return [layer.name for layer in self._layers]

    def sources(self):
        return tuple(layer.name for layer in self._layers)

    def merged(self):
        out = {}
        for layer in self._layers:
            out = merge_dicts(out, layer.data)
        return out


class ConfigStack(object):
    """分层配置栈：层进显式管道，声明顺序即优先级（defaults < file < env）。"""

    def __init__(self):
        self._pipeline = _LayerPipeline()

    def add_layer(self, name, data):
        if not isinstance(data, dict):
            raise TypeError(
                "layer %s: expected dict, got %s" % (name, type(data).__name__)
            )
        self._pipeline.append(name, data)

    def add_file(self, name, path):
        self.add_layer(name, _read_json(path))

    def apply_env(self, prefix):
        self._pipeline.append("env", _parse_env(prefix))

    def layers(self):
        return self._pipeline.names()

    def as_dict(self):
        return self._pipeline.merged()

    def _lookup(self, key):
        cur = self.as_dict()
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
            raise MissingKeyError(key, self._pipeline.sources(), _ERR_MISSING)
        return v

    def require_int(self, key):
        v, ok = self._lookup(key)
        if not ok:
            raise MissingKeyError(key, self._pipeline.sources(), _ERR_INT)
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
            raise MissingKeyError(name, self._pipeline.sources(), _ERR_SECTION)
        return v


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def required_subset(mapping, keys, source):
    """从 mapping 里挑出必选键。缺键按 source 报错。"""
    out = {}
    for k in keys:
        if k not in mapping:
            raise MissingKeyError(k, source, _ERR_SUBSET)
        out[k] = mapping[k]
    return out


def load_config(defaults, file_path, env_prefix):
    """网关用的标准入口。层顺序在管道里显式声明：defaults -> file -> env。"""
    stack = ConfigStack()
    stack.add_layer("defaults", defaults)
    stack.add_file("file", file_path)
    stack.apply_env(env_prefix)
    return stack
