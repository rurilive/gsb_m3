"""空白分词：面板最初那一版的切分口径。

规则就这么点：任何空白连续段都是分隔符，切完即丢，剩下的字符原样留在
词里。引号、反斜杠、井号此刻都只是普通字符，没有任何特殊含义，所以带
引号的命令会被切得七零八落，这是面板侧栏被吐槽最多的地方。

口径细节：
  - 空白按 Python 正则 \\s 的口径，\\t \\n \\r \\v \\f 与全角空格都算
  - 空串与纯空白都得到空列表，绝不吐出空词
  - 只认 str，其余类型抛 TypeError
"""

import re

_WHITESPACE_RUN = re.compile(r"\s+")


def split_words(text):
    """按空白把一段文本切成词列表，保持出现顺序。"""
    _require_text(text)
    return [word for word in _WHITESPACE_RUN.split(text) if word]


def _require_text(text):
    if not isinstance(text, str):
        raise TypeError("待切分的内容必须是 str，收到 {}".format(type(text).__name__))
