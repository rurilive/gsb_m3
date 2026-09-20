"""templet 现状演示：变量、过滤器、for/if、自动转义与 include。"""

from templet import Engine, TemplateCycleError

INVOICE = """\
尊敬的 {{ customer.name }}：

  订单 {{ order_id }} 共 {{ items | length }} 项，明细如下：
{% for name, price in items %}  - {{ name }}    ￥{{ price }}
{% endfor %}
{% if total >= 1000 %}  您是本月大额客户，已附赠运费券。
{% else %}  满 1000 元可附赠运费券，还差 ￥{{ short }}。
{% endif %}
  客服备注：{{ remark }}
"""

PAGE = """\
<h1>{{ title }}</h1>
<p>{{ user_input }}</p>
<p>{{ user_input | safe }}</p>
"""

HEADER = """\
<header>templet 运营页 · {{ site }}</header>
"""

FOOTER = """\
<footer>© {{ year }} {{ site }} · 联系客服</footer>
"""

LAYOUT = """\
{% include "header.html" %}
<main>
  <h1>{{ title }}</h1>
  <p>{{ body }}</p>
</main>
{% include "footer.html" %}
"""


def main():
    print("=== 订单邮件（for / if / 过滤器） ===")
    engine = Engine()
    body = engine.render_string(INVOICE, {
        "customer": {"name": "杭州·橘子科技"},
        "order_id": "SO-2042",
        "items": [("前端监控SaaS", 680), ("压测服务", 350)],
        "total": 1030,
        "short": 320,
        "remark": "发票抬头已登记",
    })
    print(body)

    print("=== 自动转义（默认开，safe 关闭） ===")
    print(engine.render_string(PAGE, {
        "title": "用户留言",
        "user_input": '<script>alert("xss")</script>',
    }))

    print("=== 公共头部/底部（include 共用上下文，展开不再二次转义） ===")
    engine.register("header.html", HEADER)
    engine.register("footer.html", FOOTER)
    print(engine.render_string(LAYOUT, {
        "site": "橘子 & 云服务",
        "year": 2026,
        "title": "版本公告",
        "body": "公共片段与页面骨架共用同一套上下文变量。",
    }))

    print("=== include 深度超限 -> TemplateCycleError ===")
    e = Engine(max_include_depth=2)
    e.register("a.html", 'A{% include "b.html" %}')
    e.register("b.html", 'B{% include "c.html" %}')
    e.register("c.html", 'C{% include "a.html" %}')
    try:
        e.render("a.html")
    except TemplateCycleError as exc:
        print("TemplateCycleError:", exc)


if __name__ == "__main__":
    main()
