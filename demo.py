"""framefmt 现状演示。

第一段：定宽行编码器把一条记录拼成一行再切回来，看一遍基线行为。
第二段：预留的二进制帧编解码演示位子（见文末注释）。
"""

from framefmt import LineCodec


def main():
    print("=== 定宽行编码 ===")
    codec = LineCodec([4, 8, 3])
    values = ["id01", "alice", "42"]
    line = codec.encode(values)
    print("  字段:", values)
    print("  编码行:", repr(line))
    print("  解码回:", codec.decode(line))
    print("  行宽:", codec.total_width())

    # TODO(帧格式改造): 长度前缀、字段类型、校验和、变长编码与流式解帧都补齐后，
    # 在这里加一段演示：
    # 编码一条含若干标量字段与嵌套记录的记录，打印得到的字节与长度前缀；
    # 把两个帧拼成一段字节流，逐帧解出来并打印各自内容，剩下的半帧留待下次；
    # 把一帧的负载改坏一个字节，打印校验和不符被拒绝的提示.

if __name__ == "__main__":
    main()
