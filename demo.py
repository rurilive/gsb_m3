"""framec 现状演示：组帧、跨包解码、CRC 容错。"""

from framec import AckFrame, CrcError, Decoder, Encoder


def hexdump(wire):
    return " ".join("%02x" % b for b in wire)


def main():
    enc = Encoder()
    dec = Decoder()

    print("=== 组帧（DATA / JSON / ACK） ===")
    for wire in (enc.encode("hello"),
                 enc.encode({"op": "sub", "ch": 3}),
                 enc.encode(42, AckFrame)):
        print(" ", hexdump(wire))

    print("\n=== 任意切块喂入 ===")
    stream = enc.encode("第二次") + enc.encode({"ok": True}) + enc.encode(7, AckFrame)
    for i in range(0, len(stream), 5):
        for frame in dec.feed(stream[i:i + 5]):
            print(" ", frame)

    print("\n=== CRC 篡改检测（坏帧丢弃，流继续） ===")
    f1 = enc.encode("before")
    f2 = bytearray(enc.encode("tampered"))
    f2[12] ^= 0xFF  # 翻转载荷里的一个字节
    f3 = enc.encode("after")
    frames = dec.feed(f1)
    try:
        dec.feed(bytes(f2))
    except CrcError as e:
        print("  捕获:", e)
    frames += dec.feed(f3)
    for frame in frames:
        print(" ", frame)



if __name__ == "__main__":
    main()
