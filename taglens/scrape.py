"""正则版提取：把标签名拼进正则，按名捞内容。

这是 taglens 最早的能力，外面有脚本直接吃它的返回格式。做法很土：
开始标签按 <tag 拼一段 [^>]* 吃属性，正文非贪婪吃到第一个同名闭合
标签为止，全程不看注释、不管嵌套、不做词法。由此有几个已知局限
（README 里写全了，tests 也锁着）：

- 注释里的同名标签照样被算进来；
- 属性值里出现 > 时开始标签被截断，之后取到的属性与正文都错位；
- 正文里嵌套同名标签时，在内层的闭合处提前收工；
- 找不到闭合标签就按没有处理，返回 None 或空列表。

这些不是待修的 bug，是冻结的对外语义。做新解析器时别顺手改这里。
"""

import html as _html
import re

from .errors import BadTagName

_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9:_-]*\Z")
_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")
_ATTR_RE = re.compile(
    r"([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s\"'>]+)")


def _check_html(html_text):
    if not isinstance(html_text, str):
        raise TypeError("待提取的 HTML 得是字符串")


def _check_tag(tag):
    if not isinstance(tag, str):
        raise TypeError("标签名得是字符串")
    if not _NAME_RE.match(tag):
        raise BadTagName(tag)


def _element_re(tag):
    """拼出 <tag ...>...</tag> 的正则，匹配不区分大小写。"""
    return re.compile(
        r"<%s(?=[\s/>])([^>]*)>(.*?)</%s\s*>"
        % (re.escape(tag), re.escape(tag)),
        re.S | re.I,
    )


def find_first(html_text, tag):
    """找第一个 <tag>，返回 (属性原文, 正文原文)；没找到给 None。"""
    _check_html(html_text)
    _check_tag(tag)
    m = _element_re(tag).search(html_text)
    if m is None:
        return None
    return (m.group(1), m.group(2))


def find_all(html_text, tag):
    """所有匹配，按出现顺序给 [(属性原文, 正文原文), ...]。"""
    _check_html(html_text)
    _check_tag(tag)
    return [m.groups() for m in _element_re(tag).finditer(html_text)]


def strip_tags(fragment):
    """删掉一段 HTML 里的标签，不动实体、不压空白。"""
    if not isinstance(fragment, str):
        raise TypeError("片段得是字符串")
    return _TAG_RE.sub("", fragment)


def _clean_text(fragment):
    return _WS_RE.sub(" ", _html.unescape(_TAG_RE.sub("", fragment))).strip()


def extract_text(html_text, tag):
    """第一个同名标签里的文本：剥标签、折算实体、压空白；没有给 None。"""
    got = find_first(html_text, tag)
    if got is None:
        return None
    return _clean_text(got[1])


def extract_all(html_text, tag):
    """所有同名标签的文本，按文档顺序；没有给空列表。"""
    return [_clean_text(inner) for _, inner in find_all(html_text, tag)]


def inner_html(html_text, tag):
    """第一个同名标签的正文原文，不剥标签、不折算实体；没有给 None。"""
    got = find_first(html_text, tag)
    return None if got is None else got[1]


def get_attr(html_text, tag, name):
    """第一个同名标签上某个属性的值（剥引号、折实体）；没有给 None。

    只认 name=value 形式，裸属性（如 disabled）取不到；属性段被 >
    截断时结果跟着错位。这都是冻结的语义，别拿新解析器来"修"。
    """
    if not isinstance(name, str) or not name:
        raise TypeError("属性名得是非空字符串")
    got = find_first(html_text, tag)
    if got is None:
        return None
    for m in _ATTR_RE.finditer(got[0]):
        if m.group(1).lower() == name.lower():
            value = m.group(2)
            if value[:1] in ("\"", "'"):
                value = value[1:-1]
            return _html.unescape(value)
    return None
