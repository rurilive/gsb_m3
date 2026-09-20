"""httpparse.constants：解析器里所有历史口径常量。

魔法数字（行长上限、CR/LF、空格/tab 等）统一收在这一层，
tokenizer 和 message 都不允许再写字面量数字。
"""

# 行长上限：按含换行符的整行字节数算（历史口径）
MAX_LINE_LENGTH = 8192

# 行结束符（\r\n 标准，裸 \n 历史容错也认）
CR = 13
LF = 10
CRLF = b"\r\n"

# 空白字节
SPACE = 32
TAB = 9
OWS = (SPACE, TAB)
OWS_BYTES = b" \t"

# method 允许的大写字母范围
METHOD_A = ord(b"A")
METHOD_Z = ord(b"Z")
METHOD_DASH = ord(b"-")

# 请求行 / chunk size 里的分隔符
SP = b" "
HTTP_PREFIX = b"HTTP/"
HTTP_PREFIX_LEN = len(HTTP_PREFIX)
DOT = b"."
SEMI = b";"

# 折行头的前导字节
FOLD_LEADS = (SPACE, TAB)
