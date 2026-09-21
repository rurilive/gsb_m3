"""wirepack 现状演示。

第一段：把几条记录编成字节，看 16 字节定长格式长什么样。
第二段：按奇形怪状的块喂给 RecordStream，验证跨块记录照样解出来。
第三段：量一下定长记录的解码吞吐，作为线上容量的底数。
第四段：流尾被截断时解码器怎么报错。
第五段：0x81 新帧的布局、嵌套标记与新老混流解码。
第六段：新帧解码吞吐，以及抓包脏数据下的报错与 resync。
"""

import time

from wirepack.errors import DecodeError
from wirepack.frame import Frame, pack_frame
from wirepack.records import RECORD_SIZE, Record, pack_record
from wirepack.stream import FrameDecoder, RecordStream, chunked


def sample_records():
    return [
        Record(120001, "data", "n1"),
        Record(120002, "data", "n2", flags=1),
        Record(120003, "ack", ""),
        Record(120004, "ctrl", "node-7", flags=8),
    ]


def show_layout():
    print("=== 定长记录布局（%d 字节） ===" % RECORD_SIZE)
    for record in sample_records():
        raw = pack_record(record)
        print("  %-38s %s" % (record, raw.hex(" ")))


def show_feed():
    print("=== 按块喂入 ===")
    blob = b"".join(pack_record(r) for r in sample_records())
    for size in (3, 5, 16, 40):
        stream = RecordStream()
        seen = []
        for piece in chunked(blob, size):
            seen.extend(stream.feed(piece))
        print("  每块 %-3d 字节: 解出 %d 条, pending=%d"
              % (size, len(seen), stream.pending))
    stream = RecordStream()
    print("  尾块只喂 9 字节: 解出 %d 条, pending=%d"
          % (len(stream.feed(blob[:len(blob) - 9])), stream.pending))


def show_throughput(count=200000):
    print("=== 解码吞吐 ===")
    record = Record(123456, "data", "n1")
    raw = pack_record(record)
    blob = raw * count
    start = time.perf_counter()
    stream = RecordStream()
    decoded = stream.feed(blob)
    spent = time.perf_counter() - start
    print("  %d 条定长记录 %.3f 秒，约 %.0f 条/秒"
          % (len(decoded), spent, count / spent))


def show_truncated_tail():
    print("=== 流尾截断 ===")
    stream = RecordStream()
    stream.feed(pack_record(sample_records()[0]) + b"\x00\x01\x02")
    try:
        stream.finish()
    except DecodeError as exc:
        print("  解码器报错: %s" % (exc,))


def sample_frames():
    inner = Frame(0, b"core", ext=[(1, b"v")])
    return [
        Frame(2, b"hello"),
        Frame(4, b"", ext=[(7, b"k1"), (300, b"k2")]),
        Frame(1, pack_frame(inner)),  # tag 最低位=1: payload 里再套一层
    ]


def show_frames():
    print("=== 0x81 新帧布局 ===")
    for frame in sample_frames():
        raw = pack_frame(frame)
        print("  %-52s %s" % (frame, raw.hex(" ")))
    outer = sample_frames()[-1]
    print("  tag=%d 最低位=%d -> nested=%s, unwrap=%s"
          % (outer.tag, outer.tag & 1, outer.nested, outer.unwrap()))


def show_mixed_stream():
    print("=== 新老混流 ===")
    blob = b"".join(
        [pack_record(r) for r in sample_records()[:2]]
        + [pack_frame(f) for f in sample_frames()]
        + [pack_record(r) for r in sample_records()[2:]])
    for size in (7, 16, 64):
        decoder = FrameDecoder()
        seen = []
        for piece in chunked(blob, size):
            seen.extend(decoder.feed(piece))
        decoder.finish()
        print("  每块 %-3d 字节: 解出 %d 条 (记录 %d, 帧 %d), pending=%d"
              % (size, len(seen), decoder.records, decoder.frames,
                 decoder.pending))


def show_frame_throughput(count=200000):
    print("=== 新帧解码吞吐 ===")
    raw = pack_frame(Frame(2, b"payload-1", ext=[(3, b"x")]))
    blob = raw * count
    start = time.perf_counter()
    decoder = FrameDecoder()
    decoded = decoder.feed(blob)
    spent = time.perf_counter() - start
    print("  %d 条新帧 %.3f 秒，约 %.0f 帧/秒"
          % (len(decoded), spent, count / spent))


def show_dirty_stream():
    print("=== 脏数据与 resync ===")
    good = pack_frame(Frame(2, b"ok"))
    bad_len = b"\x81\x02" + b"\xff\xff\xff\xff\x0f"  # payload_len 超上限
    bad_varint = b"\x81" + b"\xff" * 6              # tag varint 超 5 字节
    blob = good + bad_len + good + bad_varint + good + good[:-2]
    decoder = FrameDecoder()
    seen = decoder.feed(blob)
    decoder.finish()
    print("  解出 %d 帧，记录 %d 条错误:" % (len(seen), len(decoder.errors)))
    for err in decoder.errors:
        print("    %s" % (err,))


def main():
    show_layout()
    show_feed()
    show_throughput()
    show_truncated_tail()
    show_frames()
    show_mixed_stream()
    show_frame_throughput()
    show_dirty_stream()


if __name__ == "__main__":
    main()
