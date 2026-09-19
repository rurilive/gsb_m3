"""walog 现状演示：写入、重启恢复、断电模拟。"""

import os
import struct
import tempfile

from walog import KVStore


def section(title):
    print(f"=== {title} ===")


def main():
    root = tempfile.mkdtemp(prefix="walog-demo-")

    # 1) 同 key 连续写，重启恢复
    section("同 key 连续写 12 次后重启")
    d1 = os.path.join(root, "s1")
    s = KVStore(d1, max_segment_bytes=1)
    for i in range(1, 13):
        s.set("listen", f"v{i}")
    s.checkpoint()
    s.close()
    s2 = KVStore(d1, max_segment_bytes=1)
    s2.recover()
    print(f"  恢复后 listen = {s2.get('listen')}（最后一次写入是 v12）")
    s2.close()

    # 2) 长字段写入后重启
    section("300 字节字段写入后重启")
    d2 = os.path.join(root, "s2")
    s = KVStore(d2)
    s.set("cert", "A" * 300)
    s.checkpoint()
    s.close()
    s2 = KVStore(d2)
    n = s2.recover()
    print(f"  恢复记录数 = {n}, cert 长度 = {len(s2.get('cert') or '')}")
    s2.close()

    # 3) 断电模拟：最后一帧只写了一半
    section("断电后重启（尾部半帧）")
    d3 = os.path.join(root, "s3")
    s = KVStore(d3)
    s.set("k1", "v1")
    s.set("k2", "v2")
    s.checkpoint()
    payload = b'{"op":"set","key":"k9","value":"ghost","seq":99}'
    with open(os.path.join(d3, "wal-2.log"), "ab") as f:
        f.write(struct.pack("<H", len(payload)) + payload + b"\x12\x34")
    s2 = KVStore(d3)
    n = s2.recover()
    print(f"  恢复记录数 = {n}, k9 = {s2.get('k9')}")
    s2.close()

    # 4) 写入返回后立刻重启（不走 checkpoint/close，模拟进程直接没了）
    section("写入返回后立刻重启")
    d4 = os.path.join(root, "s4")
    s = KVStore(d4)
    s.set("token", "t-1")
    print(f"  set 返回后 get = {s.get('token')}")
    s2 = KVStore(d4)
    s2.recover()
    print(f"  重启后 get = {s2.get('token')}")
    s2.close()


if __name__ == "__main__":
    main()
