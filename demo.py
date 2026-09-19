"""路由现状演示。

第一段：注册几张典型路由，打印解析结果与尾斜杠行为。
第二段：注释里留了优先级与 405 演示的位子。
"""

from webpath.router import NotFound, Router


def fetch_user():
    return "user page"


def new_user_form():
    return "new user form"


def health():
    return "ok"


def show(path, result):
    print(f"  GET {path} -> {result}")


def main():
    r = Router()
    r.add_route("GET", "/health", health)
    r.add_route("GET", "/users/{id}", fetch_user)
    r.add_route("GET", "/users/new", new_user_form)

    print("=== 路由解析现状 ===")
    for p in ["/health", "/users/42", "/users/new"]:
        try:
            handler, params = r.resolve("GET", p)
            show(p, f"{handler.__name__} {params or ''}".strip())
        except NotFound:
            show(p, "404")

    print("\n=== 尾斜杠（默认严格） ===")
    for p in ["/users/42", "/users/42/", "/health/"]:
        try:
            handler, _ = r.resolve("GET", p)
            show(p, handler.__name__)
        except NotFound:
            show(p, "404")

    # TODO(路由升级): 实现静态优先与 Http405 后，在这里演示：
    # /users/new 稳定命中静态路由；对已存在的路径用错方法时
    # 抛 Http405 并打印 Allow 列表；redirect 模式下的尾斜杠重定向。


if __name__ == "__main__":
    main()
