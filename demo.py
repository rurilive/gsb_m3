"""路由现状演示。

第一段：注册几张典型路由，打印解析结果与尾斜杠行为。
第二段：注释里留了优先级与 405 演示的位子。
"""

from webpath.router import Http405, NotFound, Router


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

    print("\n=== 静态优先 ===")
    for p in ["/users/new", "/users/42"]:
        handler, params = r.resolve("GET", p)
        show(p, f"{handler.__name__} {params or ''}".strip())

    print("\n=== 打错方法（Http405） ===")
    r.add_route("POST", "/users/new", new_user_form)
    for m, p in [("DELETE", "/users/new"), ("DELETE", "/orders/1")]:
        try:
            r.resolve(m, p)
        except Http405 as e:
            print(f"  {m} {p} -> 405 Allow: {', '.join(e.allow)}")
        except NotFound:
            print(f"  {m} {p} -> 404")

    print("\n=== 尾斜杠 redirect 模式 ===")
    rr = Router(trailing="redirect")
    rr.add_route("GET", "/health", health)
    rr.add_route("GET", "/users/{id}/", fetch_user)
    for p in ["/health", "/health/", "/users/42", "/users/42/"]:
        handler, params, redirect = rr.resolve("GET", p)
        note = " (redirect)" if redirect else ""
        show(p, f"{handler.__name__} {params or ''}{note}".strip())


if __name__ == "__main__":
    main()
