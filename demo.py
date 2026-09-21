"""端到端跑一遍：整段加解密、流式分块、密钥轮换、改字节看它怎么报错。"""

import os
import tempfile

from vaultfile import (
    AuthError,
    rotate_file,
    seal,
    seal_file,
    seal_stream,
    unseal,
    unseal_file,
    unseal_stream,
)

KEY = b"demo-key-0123456789abcdef"
KEY_NEW = b"demo-key-abcdef0123456789"


def main():
    message = "对账报表 2026-09 期初余额 1204332.00 元".encode("utf-8")
    blob = seal(message, KEY)
    print("sealed %d bytes into %d bytes" % (len(message), len(blob)))
    assert unseal(blob, KEY) == message
    print("in-memory round trip ok")

    broken = bytearray(blob)
    broken[len(broken) // 2] ^= 0x01
    try:
        unseal(bytes(broken), KEY)
    except AuthError as exc:
        print("tampered byte rejected: %s" % (exc,))
    else:
        raise SystemExit("tampered container decrypted, this is a bug")

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "report.vlt")
        written = seal_file(path, message, KEY)
        print("wrote %s (%d bytes on disk)" % (path, written))
        assert unseal_file(path, KEY) == message
        print("file round trip ok")

        # 流式分块：报表几百 MB 也按块走，峰值内存只跟块大小走。
        plain_path = os.path.join(tmp, "big-report.bin")
        stream_path = os.path.join(tmp, "big-report.vlt2")
        opened_path = os.path.join(tmp, "big-report.out")
        with open(plain_path, "wb") as handle:
            handle.write(message * 10000)
        seal_stream(plain_path, stream_path, KEY, chunk_size=4096)
        unseal_stream(stream_path, opened_path, {1: KEY})
        with open(opened_path, "rb") as handle:
            assert handle.read() == message * 10000
        print("streamed chunked round trip ok (4096-byte blocks)")

        # 轮换：只换第 2、3 块的密钥，区间外的块原样搬运。
        keyring = {1: KEY, 2: KEY_NEW}
        rotated = rotate_file(
            stream_path,
            new_key=keyring,
            start=2,
            end=4,
            new_key_version=2,
        )
        unseal_stream(stream_path, opened_path, keyring)
        with open(opened_path, "rb") as handle:
            assert handle.read() == message * 10000
        print("rotated %d blocks to key version 2, mixed versions unseal ok"
              % (rotated,))

        # 分块容器改一个字节：报错里带块号，解不出任何明文。
        with open(stream_path, "rb") as handle:
            blob = bytearray(handle.read())
        blob[25 + 14] ^= 0x01
        broken_path = os.path.join(tmp, "broken.vlt2")
        with open(broken_path, "wb") as handle:
            handle.write(bytes(blob))
        try:
            unseal_stream(broken_path, os.path.join(tmp, "broken.out"), KEY)
        except AuthError as exc:
            print("tampered block rejected: %s" % (exc,))
        else:
            raise SystemExit("tampered chunk decrypted, this is a bug")


if __name__ == "__main__":
    main()
