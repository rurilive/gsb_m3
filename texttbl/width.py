"""texttbl.width：显示宽度的纯函数，缓存在此收口。"""

# 列宽缓存（模块级，历史原因保留，但只准经由 measure() 读写）
_WIDTH_CACHE = {}


def text_width(s):
    """显示宽度（纯函数）。历史口径：按 len() 算，中文也按 1 个宽。"""
    return len(s)


def measure(s):
    """带缓存的 text_width。缓存的唯一出入口。"""
    if s in _WIDTH_CACHE:
        return _WIDTH_CACHE[s]
    w = text_width(s)
    _WIDTH_CACHE[s] = w
    return w
