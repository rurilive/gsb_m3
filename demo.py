"""framec 现状演示：组帧、跨包解码、CRC 容错。"""

import time

from framec import AckFrame, CrcError, Decoder, Encoder
from framec.heartbeat import PingFrame, PongFrame, VersionFrame


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

    print("\n=== 心跳往返（PING/PONG 时间戳配对） ===")
    enc2, dec2 = Encoder(), Decoder()
    sent_ns = time.monotonic_ns()
    ping = dec2.feed(enc2.encode(sent_ns, PingFrame))[0]
    print("  ", ping)
    pong = dec2.feed(enc2.encode(ping.value, PongFrame))[0]
    print("  ", pong)
    rtt_ns = time.monotonic_ns() - pong.value
    print("   RTT = %d ns（PONG 回显 PING 时间戳）" % rtt_ns)

    print("\n=== 版本握手（VERSION 互报版本） ===")
    for who, versions in (("本地", [1, 3]), ("对端", [1])):
        frame = dec2.feed(enc2.encode(versions, VersionFrame))[0]
        payload = enc2.encode(versions, VersionFrame)[10:-4]
        print("   %s: %r  载荷 %r" % (who, frame, payload))
    local, remote = {1, 3}, {1}
    print("   协商结果: 共同支持版本 %s" % sorted(local & remote))


if __name__ == "__main__":
    main()
