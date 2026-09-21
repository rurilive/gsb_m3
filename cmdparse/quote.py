"""规范引用：把词素文本包回命令行时，保证再解析能得到一模一样的词。

口径与 shlex.quote 同款（shlex 在本项目里只做对拍参照，这里自己实现，
纯标准库）：

  - 空串引用成 ''，空词也能活下来
  - 只含 \"安全字符\"（ASCII 字母数字与 @%+=:,./-）的串原样返回
  - 其余一律单引号包起来；串里的单引号走 '\'' 拼接
    （关掉单引号、双引号包一个单引号、再开单引号）

这样 quote_word 出来的多个词用单个空格拼回去再 tokenize，每个词的
text 与原来逐词一致；安全字符不含空格，所以空格分隔不会被歧义掉。
"""

import re

_FIND_UNSAFE = re.compile(r"[^\w@%+=:,./-]", re.ASCII).search


def quote_word(text):
    """返回 text 的规范引用形式，空串给 "''"。"""
    if not isinstance(text, str):
        raise TypeError(
            "待引用的词必须是 str，收到 {}".format(type(text).__name__))
    if not text:
        return "''"
    if _FIND_UNSAFE(text) is None:
        return text
    return "'" + text.replace("'", "'\"'\"'") + "'"
