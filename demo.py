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

    print("\n=== 心跳往返（PING / PONG） ===")
    sent = time.monotonic_ns()
    ping = dec.feed(enc.encode(sent, PingFrame))[0]
    pong = dec.feed(enc.encode(ping.value, PongFrame))[0]  # 对端原样回显
    print("  PING  ts=%d" % ping.value)
    print("  PONG  echo=%d RTT=%d ns" % (pong.value, time.monotonic_ns() - pong.value))

    print("\n=== 版本握手（VERSION） ===")
    local_version = [1, 3]
    peer_version = dec.feed(enc.encode(local_version, VersionFrame))[0].value
    print("  本端 -> 对端:", peer_version)
    print("  对端 -> 本端:", dec.feed(enc.encode([2, 0, 9], VersionFrame))[0].value)



if __name__ == "__main__":
    main()
