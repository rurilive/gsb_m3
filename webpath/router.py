"""方法 + 路径的路由表。

add_route 注册路由，resolve 解析出 handler 与路径参数。
静态段多的路由优先匹配，静态段数相同按注册顺序。
"""


class NotFound(Exception):
    """路径或方法没有匹配到任何路由。"""


class Http405(NotFound):
    """方法无匹配，但同形状的路径注册在别的方法下。

    allow 为按注册顺序去重后的可用方法列表。
    """

    def __init__(self, message, allow):
        super().__init__(message)
        self.allow = allow


class Router:
    """静态段优先的路由表。"""

    def __init__(self, trailing="strict"):
        """trailing="strict"：尾斜杠必须精确一致；
        trailing="redirect"：允许去/补尾斜杠重定向命中。"""
        if trailing not in ("strict", "redirect"):
            raise ValueError(f"unknown trailing policy: {trailing!r}")
        self._trailing = trailing
        # [(method, segments, handler)] 按注册顺序保存
        self._routes = []

    def add_route(self, method, path, handler):
        """注册一条路由。path 中的 {name} 段提取为路径参数。"""
        self._routes.append((method, _split(path), handler))

    def resolve(self, method, path):
        """解析请求。

        strict 模式返回 (handler, params)；redirect 模式返回
        (handler, params, need_redirect)。方法错但路径形状存在抛
        Http405，路径不存在抛 NotFound。
        """
        segments = _split(path)
        found = self._match_method(method, segments)
        if found is not None:
            handler, params = found
            if self._trailing == "redirect":
                return handler, params, False
            return handler, params
        if self._trailing == "redirect":
            toggled = segments[:-1] if segments and segments[-1] == "" else segments + [""]
            found = self._match_method(method, toggled)
            if found is not None:
                handler, params = found
                return handler, params, True
        allow = self._allowed_methods(method, segments)
        if allow:
            raise Http405(f"method {method} not allowed for {path}", allow)
        raise NotFound(f"no route for {method} {path}")

    def _match_method(self, method, segments):
        """在 method 下按优先级找第一个命中，返回 (handler, params) 或 None。"""
        for route_method, pattern, handler in self._prioritized():
            if route_method != method:
                continue
            params = _match(pattern, segments)
            if params is not None:
                return handler, params
        return None

    def _prioritized(self):
        """静态段多的排前面；并列时 sorted 稳定，保持注册顺序。"""
        return sorted(self._routes, key=lambda r: -_static_count(r[1]))

    def _allowed_methods(self, method, segments):
        """其它方法下同形状（段数与静态段一致）路由的方法，按注册序去重。"""
        allow = []
        for route_method, pattern, _ in self._routes:
            if route_method == method or route_method in allow:
                continue
            if _same_shape(pattern, segments):
                allow.append(route_method)
        return allow


def _static_count(pattern):
    """pattern 中静态段的数量。"""
    return sum(1 for pat in pattern if not _is_param(pat))


def _is_param(pat):
    return pat.startswith("{") and pat.endswith("}")


def _same_shape(pattern, segments):
    """段数相同且静态段逐一相等（参数段不比较内容）。"""
    if len(pattern) != len(segments):
        return False
    return all(_is_param(pat) or pat == seg for pat, seg in zip(pattern, segments))


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
