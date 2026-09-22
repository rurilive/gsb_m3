"""数据文件的记录编解码。

数据文件按行追加，一行一条记录，五段空格分隔：

    seq op key value crc32

seq 是自增序号，op 是 P（写入）或 D（删除），key 不含空白字符，
value 是记录的紧凑 JSON 文本，crc32 覆盖它前面的四段。
写到一半进程没了留下的半截行（缺段、缺换行、校验和不符）
一律按损坏处理，由调用方决定丢弃还是报错。
"""

import json
import zlib


class RecordCorrupt(Exception):
    """一行记录缺段、JSON 解析失败或校验和不符。"""


def encode_line(seq, op, key, record):
    """把一条记录编码成一行字节，结尾带换行。"""
    head = ("%d %s %s " % (seq, op, key)).encode("utf-8")
    body = json.dumps(
        record, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    crc = ("%08x" % (zlib.crc32(head + body) & 0xFFFFFFFF)).encode("ascii")
    return head + body + b" " + crc + b"\n"


def decode_line(line):
    """解析一行，返回 (seq, op, key, record)，损坏时抛 RecordCorrupt。"""
    if not line.endswith(b"\n"):
        raise RecordCorrupt("没有以换行结束，像是写了一半")
    parts = line[:-1].split(b" ", 3)
    if len(parts) != 4:
        raise RecordCorrupt("字段不够")
    seq_text, op, key, rest = parts
    body, sep, crc_text = rest.rpartition(b" ")
    if not sep or not body or not crc_text:
        raise RecordCorrupt("缺 value 或校验和")
    expect = "%08x" % (
        zlib.crc32(seq_text + b" " + op + b" " + key + b" " + body) & 0xFFFFFFFF
    )
    if crc_text != expect.encode("ascii"):
        raise RecordCorrupt("校验和不符")
    if op not in (b"P", b"D"):
        raise RecordCorrupt("未知的 op: %r" % op)
    try:
        record = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise RecordCorrupt("value 不是合法 JSON")
    if not isinstance(record, dict):
        raise RecordCorrupt("value 不是 JSON 对象")
    try:
        seq = int(seq_text)
    except ValueError:
        raise RecordCorrupt("seq 不是整数")
    return seq, op.decode("ascii"), key.decode("utf-8"), record
