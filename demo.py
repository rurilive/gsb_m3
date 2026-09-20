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
<header>{{ site_name }} · {{ section }}</header>
"""

FOOTER = """\
<footer>(c) {{ site_name }}</footer>
"""

SKELETON = """\
{% include "header.html" %}
<main>{{ body }}</main>
{% include "footer.html" %}
"""

LOOPHOLE = """\
{% include "loophole.html" %}
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

    print("=== 页面骨架 include 公共片段 ===")
    engine.register("header.html", HEADER)
    engine.register("footer.html", FOOTER)
    print(engine.render_string(SKELETON, {
        "site_name": "橘子运营台",
        "section": "活动页",
        "body": "本周大促进行中",
    }))

    print("=== include 深度超限（TemplateCycleError） ===")
    engine.register("loophole.html", LOOPHOLE)
    try:
        engine.render("loophole.html")
    except TemplateCycleError as exc:
        print("已拦截循环包含:", exc)


if __name__ == "__main__":
    main()
