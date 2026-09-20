"""tar-lite 头部布局的唯一事实来源：块尺寸、字段偏移与校验和。

读写两层都只能引用这里的常量，偏移不许在别处再写一遍。
"""

BLOCK_SIZE = 512
MAGIC = b"ARCL"

# 头部字段偏移与长度（头部正好一个块）
MAGIC_OFF = 0
MAGIC_LEN = 4
NAME_OFF = 4
NAME_LEN = 64
SIZE_OFF = 68
SIZE_LEN = 8
CHECKSUM_OFF = 76
CHECKSUM_LEN = 4

# 数据区按块对齐；归档以两个全零块收尾
END_BLOCKS = b"\x00" * (BLOCK_SIZE * 2)
ZERO_BLOCK = b"\x00" * BLOCK_SIZE


def header_checksum(head):
    """头部按字节求和（u32）；校验和字段按置零参与计算。"""
    return (sum(head[:CHECKSUM_OFF]) + sum(head[CHECKSUM_OFF + CHECKSUM_LEN:])) & 0xFFFFFFFF
