"""taglens：抓取脚本里的小 HTML 提取器。

眼下只有正则版提取（scrape.py）：按标签名找同名块，剥掉标签取文本，
不建树也不认选择器。下一步的规划见 README 与 demo.py 末尾的待办。
"""

from .errors import BadTagName, TaglensError
from .scrape import (extract_all, extract_text, find_all, find_first,
                     get_attr, inner_html, strip_tags)

__all__ = [
    "BadTagName",
    "TaglensError",
    "extract_all",
    "extract_text",
    "find_all",
    "find_first",
    "get_attr",
    "inner_html",
    "strip_tags",
]
