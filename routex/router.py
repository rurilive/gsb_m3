"""routex 当前实现：最朴素的线性路径匹配器。

现在只有逐条枚举比较的能力：注册进来的路径一律按整串字面量对待，
匹配时把请求路径和每一条已注册路径逐字符比较，完全相同的那条算命中。
没有前缀树，没有参数段，没有通配段，也没有最长前缀或优先级的概念，
冒号、星号这些字符在这里都只是普通字符。
"""

from collections import namedtuple

# 命中结果：handler 是注册时挂载的处理体，params 是捕获到的参数。
# 线性实现里 params 恒为空字典。
Match = namedtuple("Match", ["handler", "params"])


class RouteError(Exception):
    """routex 所有路由相关异常的基类。"""


class InvalidPathError(RouteError):
    """路径不合法。"""


class DuplicateRouteError(RouteError):
    """同一路径被重复注册。"""


class MissingRouteError(RouteError):
    """注销了一条没有注册过的路径。"""


def split_path(path):
    """把路径切成段。

    约定以斜杠开头，根路径切成空列表，其余去掉开头斜杠后按斜杠切分。
    空串、非字符串、缺前导斜杠，以及切出的空段（含尾斜杠）都判为非法。
    """
    if not isinstance(path, str):
        raise InvalidPathError("路径必须是字符串: %r" % (path,))
    if not path.startswith("/"):
        raise InvalidPathError("路径必须以斜杠开头: %r" % (path,))
    if path == "/":
        return []
    segments = path[1:].split("/")
    for seg in segments:
        if seg == "":
            raise InvalidPathError("路径里存在空段: %r" % (path,))
    return segments


class LinearRoute:
    """朴素线性路径匹配器。

    内部只维护一个按注册顺序排列的列表，匹配时顺序扫描，
    对每条路径做整串的逐字符相等比较。
    """

    def __init__(self):
        self._routes = []  # [(path, handler), ...] 注册顺序
        self._index = {}  # path -> handler，用于查重与快速注销

    def add(self, path, handler):
        """注册一条路径。同一路径重复注册直接报错。"""
        split_path(path)
        if path in self._index:
            raise DuplicateRouteError("路径已注册: %r" % (path,))
        self._routes.append((path, handler))
        self._index[path] = handler
        return self

    def remove(self, path):
        """注销一条路径。路径没注册过则报错。"""
        if path not in self._index:
            raise MissingRouteError("路径未注册: %r" % (path,))
        del self._index[path]
        self._routes = [(p, h) for (p, h) in self._routes if p != path]

    def match(self, path):
        """按注册顺序逐条做整串比较，完全相同的第一条命中，否则返回 None。"""
        split_path(path)
        for route_path, handler in self._routes:
            if route_path == path:
                return Match(handler, {})
        return None

    def routes(self):
        """列出全部已注册路径，按注册顺序。"""
        return [p for (p, _h) in self._routes]
