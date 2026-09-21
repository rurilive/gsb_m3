"""v2 分块容器：定长分块的流式加解密与密钥轮换。

v2 文件布局：

    file_header(25) | chunk*

file_header：

    magic(4)="VLT2" | fmt(1)=2 | salt(16) | chunk_size(4 大端)

每个 chunk：

    key_version(1) | flags(1) | index(8 大端) | length(4 大端)
    | ciphertext(length) | tag(32)

flags 最低位是 final 标记，最后一块（含空文件时唯一的空块）必须带。
length 是该块明文也是密文的字节数，除最后一块外都等于 file_header 里
的 chunk_size。tag 为 HMAC-SHA256(mac_key, file_header + chunk_header +
ciphertext)，把块钉死在它所属的文件和块号上：翻字节、块调包、块挪位、
尾巴被截都会在解对应块时炸掉，报错里带着块号。

每块的 nonce 从密钥、文件 salt 和块号派生：
derive(key, "nonce2", salt || index)，同一把密钥下跨文件（salt 随机）
跨块（index 不同）都不重样。解密严格按顺序：先按该块头部记的版本选密钥、
验 tag，过了才解密写出，一个没认证的明文字节都不吐。
"""

import contextlib
import os
import struct
import tempfile

from .format import MAGIC_V1, NONCE_LEN, SALT_LEN, TAG_LEN
from .keystream import derive, mac, verify_mac, xor_stream

MAGIC_V2 = b"VLT2"
FMT_V2 = 2
NONCE2_LABEL = b"nonce2"

DEFAULT_CHUNK_SIZE = 1 << 20
_MAX_CHUNK_SIZE = 0xFFFFFFFF

_FILE_HEADER = struct.Struct(">4sB16sI")
FILE_HEADER_LEN = _FILE_HEADER.size
_CHUNK_HEADER = struct.Struct(">BBQI")
CHUNK_HEADER_LEN = _CHUNK_HEADER.size
FLAG_FINAL = 0x01


def _validate_chunk_size(chunk_size):
    """块大小必须是正整数，且塞得进头部的 4 字节字段。"""
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise TypeError(
            "chunk_size must be an int, got %s" % (type(chunk_size).__name__)
        )
    if not 1 <= chunk_size <= _MAX_CHUNK_SIZE:
        raise ValueError(
            "chunk_size must be within [1, %d], got %d"
            % (_MAX_CHUNK_SIZE, chunk_size)
        )
    return chunk_size


def _read_exact(src, count):
    """尽量读满 count 字节，提前 EOF 就返回手里这些（可能为空）。"""
    chunks = []
    remaining = count
    while remaining:
        piece = src.read(remaining)
        if not piece:
            break
        chunks.append(piece)
        remaining -= len(piece)
    if not chunks:
        return b""
    if len(chunks) == 1:
        return chunks[0]
    return b"".join(chunks)


def _read_bounded(src, count):
    """读至多 count 字节，且手里的数据也不超过 count。

    普通文件对象 read(n) 自己就限量，但泛型流允许一次吐出比请求更多的
    字节。多出来的部分留在 _Leftover 包装里，保证明文侧峰值内存只跟
    块大小走，不被一个不听话的源撑大。
    """
    if count <= 0:
        return b""
    leftover = getattr(src, "_vaultfile_leftover", None)
    if leftover:
        piece, src._vaultfile_leftover = leftover[:count], leftover[count:]
        if len(piece) == count:
            return bytes(piece)
        count -= len(piece)
        parts = [piece]
    else:
        parts = []
    read = src.read(count)
    if read:
        if len(read) > count:
            src._vaultfile_leftover = read[count:]
            read = read[:count]
        parts.append(read)
    if not parts:
        return b""
    return parts[0] if len(parts) == 1 and isinstance(parts[0], bytes) else b"".join(parts)


@contextlib.contextmanager
def _open_src(src):
    """路径就开文件，带 read 的流直接用，其余拒绝。"""
    if hasattr(src, "read"):
        yield src
        return
    if not isinstance(src, (str, bytes, os.PathLike)):
        raise TypeError(
            "src must be a path or a binary readable stream, got %s"
            % (type(src).__name__)
        )
    with open(src, "rb") as handle:
        yield handle


@contextlib.contextmanager
def _open_dst(dst):
    """写流直接写；写路径先落同目录临时文件，成功才原子替换。"""
    if hasattr(dst, "write"):
        yield dst
        return
    if not isinstance(dst, (str, bytes, os.PathLike)):
        raise TypeError(
            "dst must be a path or a binary writable stream, got %s"
            % (type(dst).__name__)
        )
    directory = os.path.dirname(os.path.abspath(dst))
    fd, tmp_path = tempfile.mkstemp(prefix=".vlt2-", dir=directory)
    handle = os.fdopen(fd, "wb")
    try:
        yield handle
    except BaseException:
        handle.close()
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise
    else:
        handle.close()
        os.replace(tmp_path, dst)


def _block_nonce(selected_key, salt, index):
    """块 nonce：密钥 + 文件随机量 + 块号三者绑定。"""
    info = salt + index.to_bytes(8, "big")
    return derive(selected_key, NONCE2_LABEL, info)[:NONCE_LEN]


def seal_stream(src, dst, key, key_version=None, chunk_size=DEFAULT_CHUNK_SIZE):
    """流式加密：从 src 读到 dst 写，每次只在手里留一个块。

    src/dst 可以是路径，也可以是二进制文件对象（BytesIO 等）。
    返回写出去的容器字节数。空明文也产出一块带 final 的空块。
    """
    from .vault import DEFAULT_KEY_VERSION, _subkeys, select_key

    _validate_chunk_size(chunk_size)
    version = DEFAULT_KEY_VERSION if key_version is None else key_version
    selected = select_key(key, version)
    salt = os.urandom(SALT_LEN)
    enc_key, mac_key = _subkeys(selected, salt)
    file_header = _FILE_HEADER.pack(MAGIC_V2, FMT_V2, salt, chunk_size)

    written = 0
    with _open_src(src) as reader, _open_dst(dst) as writer:
        writer.write(file_header)
        written += len(file_header)

        index = 0
        block = _read_bounded(reader, chunk_size)
        while True:
            next_block = _read_bounded(reader, chunk_size)
            final = not next_block
            nonce = _block_nonce(selected, salt, index)
            ciphertext = xor_stream(enc_key, nonce, block)
            flags = FLAG_FINAL if final else 0
            chunk_header = _CHUNK_HEADER.pack(
                version, flags, index, len(ciphertext)
            )
            tag = mac(mac_key, file_header + chunk_header + ciphertext)
            writer.write(chunk_header)
            writer.write(ciphertext)
            writer.write(tag)
            written += len(chunk_header) + len(ciphertext) + len(tag)
            if final:
                break
            index += 1
            block = next_block
    return written


def _subkeys_cached(version, keyring, salt, cache):
    """按版本取该块的 (selected, enc_key, mac_key)，同一版本只派生一次。"""
    if version not in cache:
        from .vault import _subkeys, select_key

        selected = select_key(keyring, version)
        enc_key, mac_key = _subkeys(selected, salt)
        cache[version] = (selected, enc_key, mac_key)
    return cache[version]


def _auth(message):
    from .vault import AuthError

    return AuthError(message)


def _unseal_v2(reader, file_header, keyring, writer):
    """解一个已经读过文件头的 v2 流，返回写出的明文字节数。"""
    _magic, fmt, salt, chunk_size = _FILE_HEADER.unpack(file_header)
    if fmt != FMT_V2:
        raise _auth("unsupported chunked format version %d" % (fmt,))
    if chunk_size == 0:
        raise _auth("file header declares chunk_size 0")

    key_cache = {}
    expected_index = 0
    saw_final = False
    written = 0

    while True:
        header_bytes = _read_exact(reader, CHUNK_HEADER_LEN)
        if not header_bytes:
            break
        if len(header_bytes) < CHUNK_HEADER_LEN:
            raise _auth("truncated block header at block %d" % (expected_index,))
        version, flags, index, length = _CHUNK_HEADER.unpack(header_bytes)
        if saw_final:
            raise _auth(
                "block %d appears after the final block %d"
                % (index, expected_index - 1)
            )
        if flags & ~FLAG_FINAL:
            raise _auth("unknown flags 0x%02x at block %d" % (flags, index))
        if length > chunk_size:
            raise _auth(
                "block %d claims length %d larger than chunk size %d"
                % (index, length, chunk_size)
            )

        ciphertext = _read_exact(reader, length)
        if len(ciphertext) < length:
            raise _auth(
                "block %d is truncated: want %d ciphertext bytes, got %d"
                % (index, length, len(ciphertext))
            )
        tag = _read_exact(reader, TAG_LEN)
        if len(tag) < TAG_LEN:
            raise _auth("block %d is missing its tag" % (index,))

        selected, enc_key, mac_key = _subkeys_cached(
            version, keyring, salt, key_cache
        )
        if not verify_mac(mac_key, file_header + header_bytes + ciphertext, tag):
            raise _auth(
                "tag mismatch at block %d, container was altered" % (index,)
            )
        if index != expected_index:
            raise _auth(
                "block %d is out of place, expected block %d: chunk was "
                "swapped or moved" % (index, expected_index)
            )

        nonce = _block_nonce(selected, salt, index)
        plaintext = xor_stream(enc_key, nonce, ciphertext)
        writer.write(plaintext)
        written += length
        expected_index += 1
        if flags & FLAG_FINAL:
            saw_final = True
            break

    if not saw_final:
        raise _auth(
            "container is truncated: final block missing, last verified "
            "block %d" % (expected_index - 1)
        )
    return written


def unseal_stream(src, dst, key):
    """流式解密：v2 分块容器逐块验签解密，v1 老容器整段读入走老路。

    每块先按头部记的密钥版本选密钥、验 tag，过了才解密写 dst。篡改、
    调包、挪位、截尾都抛 AuthError，消息里带块号。返回明文字节数。
    """
    with _open_src(src) as reader, _open_dst(dst) as writer:
        magic = _read_exact(reader, 4)
        if not magic:
            raise _auth("container is empty")
        if magic == MAGIC_V1:
            from .vault import unseal

            plaintext = unseal(magic + reader.read(), key)
            writer.write(plaintext)
            return len(plaintext)
        if magic != MAGIC_V2:
            raise _auth("bad magic %r, not a vaultfile container" % (magic,))

        rest = _read_exact(reader, FILE_HEADER_LEN - 4)
        if len(rest) < FILE_HEADER_LEN - 4:
            raise _auth("file header is truncated")
        file_header = magic + rest
        return _unseal_v2(reader, file_header, key, writer)


def rotate_file(
    src,
    dst=None,
    new_key=None,
    start=0,
    end=None,
    new_key_version=None,
):
    """把 [start, end) 半开区间内的块重加密成新密钥。

    区间外的块连同文件头按原样字节搬运；区间内的块先用旧密钥验签解密，再用
    新密钥重加密、重打 tag。new_key 可以是裸密钥，也可以是 {版本: 密钥}
    密钥环——轮换混排文件时传密钥环，旧块按各自头部版本取旧密钥，
    new_key_version 指定新块写的版本。文件 salt 不变，轮换后新旧版本混排，
    unseal_stream 按每块版本取密钥。dst 缺省原地原子替换。返回轮换块数。
    """
    if new_key is None:
        raise TypeError("rotate_file requires new_key")
    for name, value in (("start", start), ("end", end)):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("%s must be a non-negative int" % (name,))
    if end is not None and start > end:
        raise ValueError("start (%d) is after end (%d)" % (start, end))

    if dst is None:
        if hasattr(src, "read"):
            raise ValueError("dst is required when src is a stream")
        dst = src

    from .vault import DEFAULT_KEY_VERSION, _subkeys, select_key

    new_version = (
        DEFAULT_KEY_VERSION if new_key_version is None else new_key_version
    )
    new_selected = select_key(new_key, new_version)

    old_cache = {}
    rotated = 0

    with _open_src(src) as reader, _open_dst(dst) as writer:
        magic = _read_exact(reader, 4)
        if magic == MAGIC_V1:
            raise _auth(
                "rotate_file only works on chunked v2 (VLT2) containers; "
                "unseal the v1 container and seal_stream it instead"
            )
        if magic != MAGIC_V2:
            raise _auth("bad magic %r, not a vaultfile container" % (magic,))
        rest = _read_exact(reader, FILE_HEADER_LEN - 4)
        if len(rest) < FILE_HEADER_LEN - 4:
            raise _auth("file header is truncated")
        file_header = magic + rest
        _magic2, fmt, salt, chunk_size = _FILE_HEADER.unpack(file_header)
        if fmt != FMT_V2:
            raise _auth("unsupported chunked format version %d" % (fmt,))
        new_enc, new_mac = _subkeys(new_selected, salt)
        writer.write(file_header)

        index = 0
        while True:
            header_bytes = _read_exact(reader, CHUNK_HEADER_LEN)
            if not header_bytes:
                break
            if len(header_bytes) < CHUNK_HEADER_LEN:
                raise _auth("truncated block header at block %d" % (index,))
            version, flags, block_index, length = _CHUNK_HEADER.unpack(header_bytes)
            if block_index != index:
                raise _auth(
                    "block %d is out of place, expected block %d"
                    % (block_index, index)
                )
            ciphertext = _read_exact(reader, length)
            if len(ciphertext) < length:
                raise _auth("block %d ciphertext is truncated" % (index,))
            tag = _read_exact(reader, TAG_LEN)
            if len(tag) < TAG_LEN:
                raise _auth("block %d is missing its tag" % (index,))

            in_range = start <= index and (end is None or index < end)
            if in_range:
                old_selected, old_enc, old_mac = _subkeys_cached(
                    version, new_key, salt, old_cache
                )
                if not verify_mac(
                    old_mac, file_header + header_bytes + ciphertext, tag
                ):
                    raise _auth(
                        "tag mismatch at block %d, refusing to rotate an "
                        "altered container" % (index,)
                    )
                nonce = _block_nonce(old_selected, salt, index)
                plaintext = xor_stream(old_enc, nonce, ciphertext)
                new_nonce = _block_nonce(new_selected, salt, index)
                new_ciphertext = xor_stream(new_enc, new_nonce, plaintext)
                new_header = _CHUNK_HEADER.pack(
                    new_version, flags, index, len(new_ciphertext)
                )
                new_tag = mac(
                    new_mac, file_header + new_header + new_ciphertext
                )
                writer.write(new_header)
                writer.write(new_ciphertext)
                writer.write(new_tag)
                rotated += 1
            else:
                writer.write(header_bytes)
                writer.write(ciphertext)
                writer.write(tag)

            if flags & FLAG_FINAL:
                break
            index += 1

    return rotated
