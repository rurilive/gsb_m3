"""wirepack: 跟端上设备对接的二进制记录编解码小库。

当前线上跑的是 16 字节定长记录，编解码、按块喂入的流式解码器都在这里。
新设备开始发 0x81 打头的变长帧，Frame/FrameDecoder 负责新老混流。
"""

from wirepack.errors import DecodeError, EncodeError, FrameDecodeError, WireError
from wirepack.frame import (
    FRAME_MAGIC,
    MAX_FRAME_SIZE,
    VARINT_MAX,
    VARINT_MAX_SIZE,
    Frame,
    encode_varint,
    pack_frame,
    unpack_frame,
)
from wirepack.records import (
    KINDS,
    LABEL_SIZE,
    MAX_SEQ,
    RECORD_SIZE,
    Record,
    decode_label,
    encode_label,
    pack_record,
    unpack_record,
)
from wirepack.stream import FrameDecoder, RecordStream, chunked, iter_records

__all__ = [
    "DecodeError",
    "EncodeError",
    "FRAME_MAGIC",
    "Frame",
    "FrameDecodeError",
    "FrameDecoder",
    "KINDS",
    "LABEL_SIZE",
    "MAX_FRAME_SIZE",
    "MAX_SEQ",
    "RECORD_SIZE",
    "Record",
    "RecordStream",
    "VARINT_MAX",
    "VARINT_MAX_SIZE",
    "WireError",
    "chunked",
    "decode_label",
    "encode_label",
    "encode_varint",
    "iter_records",
    "pack_frame",
    "pack_record",
    "unpack_frame",
    "unpack_record",
]
