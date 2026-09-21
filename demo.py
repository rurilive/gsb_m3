"""taglens 现状演示：正则提取能干什么，又在哪里露怯。

跑法：python3 demo.py
"""

import time

from taglens import extract_all, extract_text, find_first, get_attr, inner_html

PAGE = '''<!DOCTYPE html>
<html lang="zh">
<body>
  <h1 id="title">抓取小工具</h1>
  <div class="card">
    <p>第一段 <b>加粗</b> 收尾</p>
    <p class="note">第二段 &amp; 实体</p>
  </div>
  <!-- 注释里也塞了一对 <p>假段落</p> -->
</body>
</html>
'''


def show_extract():
    print("=== 按标签名提取 ===")
    print("  h1 文本:", extract_text(PAGE, "h1"))
    print("  第一个 p:", extract_text(PAGE, "p"))
    print("  全部 p:", extract_all(PAGE, "p"))
    print("  div 的 class:", get_attr(PAGE, "div", "class"))
    print("  第一个 p 的正文原文:", repr(inner_html(PAGE, "p")))


def show_limits():
    print("=== 已知局限 ===")
    nested = '<div id="outer"><div id="inner">内层</div>尾部</div>'
    print("  嵌套同名 div ->", repr(extract_text(nested, "div")))
    tricky = '<a title="1 > 2" href="/x">去</a>'
    print("  属性带尖括号 ->", repr(find_first(tricky, "a")))
    print("  标签没闭合 ->", repr(extract_text("<p>没闭合就走", "p")))


def show_scan_cost():
    print("=== 扫描代价（一遍全串正则）===")
    page = PAGE * 4000
    start = time.perf_counter()
    got = extract_all(page, "p")
    all_cost = (time.perf_counter() - start) * 1000.0
    start = time.perf_counter()
    extract_text(page, "table")  # 不存在的标签，得扫完全文
    miss_cost = (time.perf_counter() - start) * 1000.0
    print("  %.1f KB 的文档：全部 p 共 %d 个，%.1f ms；找不存在的 table，%.1f ms"
          % (len(page) / 1024.0, len(got), all_cost, miss_cost))


# TODO(解析树、选择器、往返): taglens/parser.py、taglens/select.py、
# taglens/render.py 落地之后，在这里补四段演示：
# 1) parse_document 把页面建成树，render 往返输出，跟原始 HTML 对照
# 2) select 演示标签、类、id、后代与子代、属性选择器，打印文档顺序
# 3) 随机畸形语料下跟 html.parser 对拍标签与文本事件序列
# 4) 几 MB 文档上解析加选择的计时


def main():
    show_extract()
    show_limits()
    show_scan_cost()


if __name__ == "__main__":
    main()
