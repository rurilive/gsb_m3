"""端到端跑一遍：加密、解回、改一个字节看它怎么报错。"""

import os
import tempfile

from vaultfile import AuthError, seal, seal_file, unseal, unseal_file

KEY = b"demo-key-0123456789abcdef"


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


if __name__ == "__main__":
    main()
