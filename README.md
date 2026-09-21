# taglens

抓取脚本里用的小 HTML 提取器，纯标准库，无外部依赖。

## 现状

`taglens/scrape.py` 是正则版提取，按标签名找同名块：

- `extract_text(html, tag)`：第一个同名标签里的文本（剥标签、折算实体、
  压空白），没有给 None
- `extract_all(html, tag)`：全部同名匹配的文本列表，按文档顺序
- `find_first(html, tag)` / `find_all(html, tag)`：返回 `(属性原文, 正文原文)`
- `inner_html(html, tag)`：第一个匹配的正文原文
- `strip_tags(fragment)`：删标签，不动实体与空白
- `get_attr(html, tag, name)`：第一个匹配标签上的属性值

`taglens/errors.py` 里 `TaglensError` 是输入错误的基类，`BadTagName` 是它
子类。标签名不合法抛 `BadTagName`，HTML 不是字符串抛 `TypeError`。
匹配不区分大小写。

### 已知局限（语义冻结）

下面几条是现状语义，tests 锁着，不要顺手"修"：

- 不认注释，注释里的同名标签照样被算进来
- 属性值里带 `>` 会截断开始标签，取到的属性与正文一起错位
- 正文里嵌套同名标签时，非贪婪会在内层的闭合处提前收工
- 找不到闭合标签按没有处理，给 None 或空列表
- `get_attr` 只认 `name=value`，裸属性取不到

## 运行

```bash
python3 demo.py                           # 现状演示
python3 -m unittest discover -s tests -v  # 行为基线
```

## 约定

- 纯标准库，不引入三方依赖
- 解析自己写词法建树，不靠 `html.parser`；它可以在测试里当对拍参照
- `tests/` 是行为基线，实现新能力时保持全绿，基线测试不做修改
