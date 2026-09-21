"""规范引用：把词素文本包回一条可以重新解析的命令行片段。

口径与 POSIX 常见做法（``shlex.quote``）一致，保证往返：
``tokenize`` 解析 ``quote_word(text)`` 得到的唯一词素，文本与 ``text``
一模一样。空串活成 ``''``；只含安全字符的词原样不包；其余一律套单引号，
词里的单引号拆成 ``'\"'\"'``。单引号内一切字面，所以这是最省心也最
规范的包法。
"""

# 安全字符：ASCII 字母数字加常见的 shell 元符号，跟 shlex.quote 同口径。
# 注意非 ASCII（汉字、全角空格）走“不安全”分支套单引号，宁可多包。
_SAFE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "_-.,/:=@%+"
)


def quote_word(text):
    """把词素文本规范引用成命令行片段。"""
    if not isinstance(text, str):
        raise TypeError(
            "待引用的词必须是 str，收到 {}".format(type(text).__name__)
        )
    if text == "":
        return "''"
    if all(char in _SAFE_CHARS for char in text):
        return text
    return "'" + text.replace("'", "'\"'\"'") + "'"
