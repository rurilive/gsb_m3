"""routex 现状演示。

第一段：看现有朴素线性匹配的静态路径。
第二段：预留的迭代演示位子（见文末注释）。
"""

from routex import LinearRoute


def baseline_demo():
    r = LinearRoute()
    r.add("/users", lambda: "users-list")
    r.add("/users/profile", lambda: "profile")

    print("=== 静态路径匹配（现有能力） ===")
    print("  routes()               ->", r.routes())
    m = r.match("/users")
    print("  match('/users')        -> handler=%r params=%r" % (m.handler(), m.params))
    m = r.match("/users/profile")
    print("  match('/users/profile')-> handler=%r params=%r" % (m.handler(), m.params))
    print("  match('/users/42')     ->", r.match("/users/42"))
    print("  说明：现在只有整串逐字符比较，参数段与通配段都还不认识。")


# TODO(前缀树路由改造): 段树、参数段与通配段就位后，在这里补一段演示：
# 注册形如 /users/:id 的参数路由与形如 /static/*rest 的通配路由，
# 演示匹配 /users/42 能把 42 提取进 params 里的 id，
# 演示通配段吃下剩余全部段并把捕获放进 params，
# 再注册 /users/:id 与 /users/*rest 这类同前缀的多条规则，
# 打印同一路径下按静态优于参数优于通配选出来的那条，确认优先级口径。


if __name__ == "__main__":
    baseline_demo()
