"""方法 + 路径的路由表。

add_route 注册路由，resolve 解析出 handler 与路径参数。
解析按注册顺序进行，第一个命中的路由生效。
"""


class NotFound(Exception):
    """路径或方法没有匹配到任何路由。"""


class Router:
    """注册顺序决胜负的路由表。"""

    def __init__(self):
        # [(method, segments, handler)] 按注册顺序保存
        self._routes = []

    def add_route(self, method, path, handler):
        """注册一条路由。path 中的 {name} 段提取为路径参数。"""
        self._routes.append((method, _split(path), handler))

    def resolve(self, method, path):
        """解析请求，返回 (handler, params)。无匹配抛 NotFound。"""
        segments = _split(path)
        for route_method, pattern, handler in self._routes:
            if route_method != method:
                continue
            params = _match(pattern, segments)
            if params is not None:
                return handler, params
        raise NotFound(f"no route for {method} {path}")


def _split(path):
    """路径切成段。尾斜杠会产生一个空段，因此 /foo 与 /foo/ 不同。"""
    return path.split("/")[1:]


def _match(pattern, segments):
    """pattern 与 segments 逐段比对，成功返回参数 dict，失败返回 None。"""
    if len(pattern) != len(segments):
        return None
    params = {}
    for pat, seg in zip(pattern, segments):
        if pat.startswith("{") and pat.endswith("}"):
            if seg == "":
                return None
            params[pat[1:-1]] = seg
        elif pat != seg:
            return None
    return params
