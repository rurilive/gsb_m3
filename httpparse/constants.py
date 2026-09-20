"""httpparse.constants：解析用到的上限与字节字面量。

所有魔法数字（行长上限、CR/LF、空格/Tab 等）集中在这一层，
tokenizer 与 message 都从这里取，不再各自写裸数字。
"""

# 行长度上限：按含换行符（LF）的整行字节数算（历史口径）
MAX_LINE_LENGTH = 8192

# 行结束
CR = 13
LF = 10
CRLF = b"\r\n"
LF_BYTES = b"\n"
CR_BYTES = b"\r"

# 空白
SPACE = 32
HTAB = 9
SPACE_BYTES = b" "
HTAB_BYTES = b"\t"
BLANK = (SPACE, HTAB)
OWS_BYTES = b" \t"

# 请求行
HTTP_PREFIX = b"HTTP/"
DOT = b"."
METHOD_MIN = ord("A")
METHOD_MAX = ord("Z")
METHOD_HYPHEN = ord("-")

# chunk
CHUNK_EXT_SEMI = b";"

# 头名（小写比较用）
CONTENT_LENGTH = "content-length"
TRANSFER_ENCODING = "transfer-encoding"
CHUNKED = "chunked"
