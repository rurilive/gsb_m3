"""texttbl.width：显示宽度与换行的纯函数。

历史口径（tests/ 逐字节锁着，别改）：
- 显示宽度按 len() 算，中文等宽字符也按 1 个宽
- 换行按词贪心（连续空白算一个分隔），超长词先清行再硬切
"""

# 宽度缓存：只准 text_width 读写，别处别碰。
_WIDTH_CACHE = {}


def text_width(s):
    """显示宽度。历史口径：按 len() 算，中文也按 1 个宽。"""
    if s in _WIDTH_CACHE:
        return _WIDTH_CACHE[s]
    w = len(s)
    _WIDTH_CACHE[s] = w
    return w


def wrap_text(text, wrap):
    """把文本切成若干行。wrap<=0 不换行。

    词间换行（连续空白当一个分隔），超长词硬切。历史口径，别改。
    """
    if wrap is None or wrap <= 0:
        return [text]
    tokens = text.split()
    if len(tokens) == 0:
        return [""]
    lines = []
    cur = ""
    for word in tokens:
        while text_width(word) > wrap:
            if cur != "":
                lines.append(cur)
                cur = ""
            lines.append(word[0:wrap])
            word = word[wrap:]
        if cur == "":
            cur = word
        elif text_width(cur) + 1 + text_width(word) <= wrap:
            cur = cur + " " + word
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines
