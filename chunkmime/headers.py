"""头部块与参数的解析。

头部块里每行形如 "Name: value",行间用 CRLF 隔开,块尾的空行
不算在内;Content-Disposition 这类值除了主值还挂着一串分号隔开
的参数,参数值可能用双引号包着。
"""


def parse_header_block(block):
    """把头部块解析成 {小写名字: 值},block 不含结尾的空行。"""
    headers = {}
    for line in block.split(b"\r\n"):
        if not line:
            continue
        i = line.find(b":")
        if i < 0:
            # 没有冒号的行,当噪声跳过
            continue
        name = line[:i].strip().decode("latin-1").lower()
        value = line[i + 1:].lstrip(b" \t").decode("latin-1")
        if name:
            headers[name] = value
    return headers


def parse_params(value):
    """解析 Content-Disposition 值里的参数,返回 {小写名字: 值}。

    str 或 bytes 都行(bytes 按 latin-1 解,头部本来就是字节)。
    引号值里的反斜杠转义要还原(``\\\\"`` -> ``"``、``\\\\\\\\`` ->
    ``\\\\``),裸值取到分号为止;两种值都不去尾巴,语义与
    reference.parse_all 完全一致。
    """
    if value is None or value == "":
        return {}
    if isinstance(value, bytes):
        value = value.decode("latin-1")
    params = {}
    pos = 0
    while True:
        semi = value.find(";", pos)
        if semi < 0:
            return params
        pos = semi + 1
        while pos < len(value) and value[pos] in " \t":
            pos += 1
        eq = value.find("=", pos)
        if eq < 0:
            return params
        name = value[pos:eq].strip().lower()
        pos = eq + 1
        while pos < len(value) and value[pos] in " \t":
            pos += 1
        if not name:
            continue
        if pos < len(value) and value[pos] == '"':
            pos += 1
            chars = []
            while pos < len(value):
                ch = value[pos]
                if ch == "\\" and pos + 1 < len(value):
                    chars.append(value[pos + 1])
                    pos += 2
                    continue
                if ch == '"':
                    pos += 1
                    break
                chars.append(ch)
                pos += 1
            params[name] = "".join(chars)
        else:
            end = value.find(";", pos)
            if end < 0:
                end = len(value)
            params[name] = value[pos:end].strip()
            pos = end
    return params
