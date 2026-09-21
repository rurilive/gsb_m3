"""端到端跑一遍：加密、解回、改一个字节看它怎么报错。"""

import io
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
KEY_V2 = b"demo-rotated-key-76543210"


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

        stream_path = os.path.join(tmp, "report-stream.vlt")
        with open(stream_path, "wb") as dest, io.BytesIO(message * 4) as src:
            out_bytes = seal_stream(dest, src, KEY, chunk_size=64)
        print("streamed into %d byte chunks, %d bytes on disk" % (64, out_bytes))
        with open(stream_path, "rb") as handle:
            recovered = b"".join(unseal_stream(handle, KEY))
        assert recovered == message * 4
        print("stream round trip ok")

        with open(stream_path, "rb") as handle:
            raw = bytearray(handle.read())
        tamper_at = len(raw) // 2
        raw[tamper_at] ^= 0x01
        with open(stream_path, "wb") as handle:
            handle.write(bytes(raw))
        with open(stream_path, "rb") as handle:
            try:
                b"".join(unseal_stream(handle, KEY))
            except AuthError as exc:
                print("tampered chunk rejected: %s" % (exc,))
            else:
                raise SystemExit("tampered stream decrypted, this is a bug")

        # 把上面翻坏的字节翻回来，再演示轮换。
        raw[tamper_at] ^= 0x01
        with open(stream_path, "wb") as handle:
            handle.write(bytes(raw))

        keyring = {1: KEY, 2: KEY_V2}
        moved = rotate_file(stream_path, 2, keyring, start=1, end=3)
        print("rotated %d middle chunks onto key version 2" % moved)
        with open(stream_path, "rb") as handle:
            recovered = b"".join(unseal_stream(handle, keyring))
        assert recovered == message * 4
        with open(stream_path, "rb") as handle:
            try:
                b"".join(unseal_stream(handle, {1: KEY}))
            except Exception as exc:
                print("old-only keyring correctly fails on rotated chunk: %s" % (exc,))
            else:
                raise SystemExit("missing key version was accepted, this is a bug")
        print("mixed-version file unsealed per-chunk ok")


if __name__ == "__main__":
    main()
