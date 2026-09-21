"""seal/unseal：把一份 bytes 装进容器，或者从容器里取回来。

顺序是固定死的：先按头部里记的密钥版本挑密钥，验标签，最后才解密。
标签对不上就抛 AuthError，一个明文字节都不往外吐。
"""

import os
import tempfile

from .format import (
    CHUNK_HEADER_LEN,
    FLAG_FINAL,
    NONCE_LEN,
    SALT_LEN,
    TAG_LEN,
    V2_HEADER_LEN,
    MAGIC_V2,
    FormatError,
    pack_v1,
    pack_v2_chunk_header,
    pack_v2_file_header,
    parse_v1,
    parse_v2_chunk_header,
    parse_v2_file_header,
)
from .keystream import derive, mac, normalize_key, verify_mac, xor_stream

ENC_LABEL = b"enc"
MAC_LABEL = b"mac"
NONCE_LABEL = b"nonce"
NONCE_V2_LABEL = b"nonce-v2-chunk"
DEFAULT_KEY_VERSION = 1
DEFAULT_CHUNK_SIZE = 1 << 20
_INDEX_BYTES = 8


class VaultError(Exception):
    """vaultfile 的公共错误基类。"""


class AuthError(VaultError):
    """容器结构坏了，或者认证标签对不上，反正没解出可信明文。

    v2 分块容器出错时 ``chunk_index`` 记着出问题的块号（从 0 起）；
    文件级错误为 None。
    """

    def __init__(self, message, chunk_index=None):
        super().__init__(message)
        self.chunk_index = chunk_index


class UnknownKeyError(VaultError):
    """密钥环里找不到容器头部写的那个版本。"""


def select_key(keyring, version):
    """按版本取密钥。

    keyring 可以是 {版本: 密钥} 的映射，也可以是一把裸密钥（老用法，
    版本字段被忽略）。映射里没有这个版本就抛 UnknownKeyError。
    """
    if isinstance(keyring, dict):
        if version not in keyring:
            raise UnknownKeyError("no key for version %r" % (version,))
        return normalize_key(keyring[version])
    return normalize_key(keyring)


def _subkeys(key, salt):
    """一份文件两根子密钥：一根出密钥流，一根出标签。"""
    return derive(key, ENC_LABEL, salt), derive(key, MAC_LABEL, salt)


def seal(data, key, key_version=DEFAULT_KEY_VERSION):
    """整段加密，返回自包含的容器字节串。

    盐每次现取，所以同一份明文用同一把密钥加两次，出来的是两串字节。
    """
    if isinstance(data, bytearray):
        data = bytes(data)
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes, got %s" % (type(data).__name__,))
    selected = select_key(key, key_version)
    salt = os.urandom(SALT_LEN)
    enc_key, mac_key = _subkeys(selected, salt)
    nonce = derive(selected, NONCE_LABEL, salt)[:NONCE_LEN]
    header = pack_v1(key_version, salt, nonce, len(data))
    ciphertext = xor_stream(enc_key, nonce, data)
    tag = mac(mac_key, header + ciphertext)
    return header + ciphertext + tag


def unseal(blob, key):
    """整段解密。认不出容器、标签对不上，一律 AuthError。"""
    try:
        header, version, salt, nonce, ciphertext, tag = parse_v1(blob)
    except FormatError as exc:
        raise AuthError("container is malformed: %s" % (exc,)) from exc
    selected = select_key(key, version)
    _enc_key, mac_key = _subkeys(selected, salt)
    if not verify_mac(mac_key, header + ciphertext, tag):
        raise AuthError("tag mismatch, container was altered")
    enc_key = derive(selected, ENC_LABEL, salt)
    return xor_stream(enc_key, nonce, ciphertext)


def seal_file(path, data, key, key_version=DEFAULT_KEY_VERSION):
    """加密后写进文件，返回写出去的字节数。"""
    blob = seal(data, key, key_version)
    with open(path, "wb") as handle:
        handle.write(blob)
    return len(blob)


def unseal_file(path, key):
    """读文件解密。文件不存在让它抛 OSError，不吞。"""
    with open(path, "rb") as handle:
        blob = handle.read()
    return unseal(blob, key)


# ---------------------------------------------------------------------------
# v2：定长分块、流式
# ---------------------------------------------------------------------------


def _read_exact(handle, length):
    """读到 length 个字节为止；遇 EOF 返回手里剩下的（可能为空）。"""
    pieces = []
    remaining = length
    while remaining:
        piece = handle.read(remaining)
        if not piece:
            break
        pieces.append(piece)
        remaining -= len(piece)
    return b"".join(pieces)


def _read_all(handle):
    """流式读到 EOF，按块拼，不假设一次 read 给完全部。"""
    pieces = []
    while True:
        piece = handle.read(1 << 20)
        if not piece:
            return b"".join(pieces)
        pieces.append(piece)


def _chunk_nonce(key, salt, index):
    """每块 nonce 由密钥、文件随机量 salt 和块号派生。

    salt 保证跨文件不重样，index 保证同文件内块间不重样；密钥轮换后
    新密钥派生出一串全新的 nonce，老 nonce 不会被复用。
    """
    info = salt + index.to_bytes(_INDEX_BYTES, "big")
    return derive(key, NONCE_V2_LABEL, info)[:NONCE_LEN]


def _write_v2_chunk(
    dest,
    file_header,
    index,
    flags,
    key,
    key_version,
    salt,
    enc_key,
    mac_key,
    plaintext,
):
    """加密并写出一个块帧，返回写出的字节数。"""
    nonce = _chunk_nonce(key, salt, index)
    ciphertext = xor_stream(enc_key, nonce, plaintext)
    chunk_header = pack_v2_chunk_header(index, flags, len(ciphertext), key_version)
    tag = mac(mac_key, file_header + chunk_header + ciphertext)
    dest.write(chunk_header)
    dest.write(ciphertext)
    dest.write(tag)
    return CHUNK_HEADER_LEN + len(ciphertext) + TAG_LEN


def seal_stream(
    dest,
    src,
    key,
    key_version=DEFAULT_KEY_VERSION,
    chunk_size=DEFAULT_CHUNK_SIZE,
):
    """流式加密：从 src 定长分块读，逐块加密写进 dest，返回写出字节数。

    src/dest 都是文件型对象（分别要 read/write）。峰值内存约一块大小，
    不随文件总长涨。salt 每份文件现取，块 nonce 由密钥、salt、块号派生。
    """
    if (
        not isinstance(chunk_size, int)
        or isinstance(chunk_size, bool)
        or chunk_size < 1
    ):
        raise ValueError("chunk_size must be a positive int")
    selected = select_key(key, key_version)
    salt = os.urandom(SALT_LEN)
    enc_key = derive(selected, ENC_LABEL, salt)
    mac_key = derive(selected, MAC_LABEL, salt)
    file_header = pack_v2_file_header(key_version, salt, chunk_size)
    dest.write(file_header)

    written = V2_HEADER_LEN
    index = 0
    carry = b""
    while True:
        chunk = carry + _read_exact(src, chunk_size - len(carry))
        if len(chunk) < chunk_size:
            # EOF：手里这段就是末块；空文件也写一帧 length=0 的末块。
            written += _write_v2_chunk(
                dest, file_header, index, FLAG_FINAL,
                selected, key_version, salt, enc_key, mac_key, chunk,
            )
            return written
        # 多看一个字节：拿得到说明后面还有块，当前块不是末块；
        # 这一个字节留给下一轮，避免同块数据在内存里存两份。
        peek = src.read(1)
        if not peek:
            written += _write_v2_chunk(
                dest, file_header, index, FLAG_FINAL,
                selected, key_version, salt, enc_key, mac_key, chunk,
            )
            return written
        written += _write_v2_chunk(
            dest, file_header, index, 0,
            selected, key_version, salt, enc_key, mac_key, chunk,
        )
        carry = peek
        index += 1


def _read_v2_frame(handle, expected_index, chunk_size):
    """读一个块帧并做全部结构校验，返回 (块头, 块号, flags, 密文, 标签)。"""
    index = expected_index
    header_bytes = _read_exact(handle, CHUNK_HEADER_LEN)
    if not header_bytes:
        return None
    try:
        if len(header_bytes) < CHUNK_HEADER_LEN:
            raise FormatError("chunk %d header is truncated" % expected_index)
        chunk_header, index, flags, length, version = parse_v2_chunk_header(
            header_bytes
        )
        if index != expected_index:
            raise FormatError(
                "chunk sequence broken: expected index %d, found %d"
                % (expected_index, index)
            )
        if flags & FLAG_FINAL:
            if length > chunk_size:
                raise FormatError(
                    "chunk %d final payload %d exceeds chunk size %d"
                    % (index, length, chunk_size)
                )
        elif length != chunk_size:
            raise FormatError(
                "chunk %d is non-final but carries %d bytes, expected %d"
                % (index, length, chunk_size)
            )
        ciphertext = _read_exact(handle, length)
        if len(ciphertext) != length:
            raise FormatError("chunk %d ciphertext is truncated" % index)
        tag = _read_exact(handle, TAG_LEN)
        if len(tag) != TAG_LEN:
            raise FormatError("chunk %d tag is truncated" % index)
    except FormatError as exc:
        raise AuthError("container is malformed: %s" % (exc,), chunk_index=index)
    return chunk_header, index, flags, length, version, ciphertext, tag


def _unseal_v2(handle, file_header, keyring):
    """逐块验签解密的生成器，unseal_stream 的 v2 分支。"""
    try:
        _header, _default_version, salt, chunk_size = parse_v2_file_header(file_header)
    except FormatError as exc:
        raise AuthError("container is malformed: %s" % (exc,)) from exc

    subkeys = {}

    def keys_for(version, index):
        # 轮换后同一文件里版本混排：按每块自己的版本取一次密钥，缓存复用。
        if version not in subkeys:
            try:
                selected = select_key(keyring, version)
            except UnknownKeyError as exc:
                raise UnknownKeyError("chunk %d: %s" % (index, exc)) from exc
            subkeys[version] = (
                selected,
                derive(selected, ENC_LABEL, salt),
                derive(selected, MAC_LABEL, salt),
            )
        return subkeys[version]

    expected_index = 0
    while True:
        frame = _read_v2_frame(handle, expected_index, chunk_size)
        if frame is None:
            raise AuthError(
                "container is truncated: final chunk never appeared, "
                "last seen chunk %d" % (expected_index - 1),
                chunk_index=expected_index,
            )
        chunk_header, index, flags, length, version, ciphertext, tag = frame

        selected, enc_key, mac_key = keys_for(version, index)
        if not verify_mac(mac_key, file_header + chunk_header + ciphertext, tag):
            raise AuthError(
                "chunk %d tag mismatch, the file was altered or the chunk was swapped"
                % index,
                chunk_index=index,
            )
        nonce = _chunk_nonce(selected, salt, index)
        # 标签先过，明文这时候才允许算出来并往外吐。
        yield xor_stream(enc_key, nonce, ciphertext)

        if flags & FLAG_FINAL:
            tail = handle.read(1)
            if tail:
                raise AuthError(
                    "container carries extra bytes after the final chunk %d" % index,
                    chunk_index=index,
                )
            return
        expected_index += 1


def unseal_stream(src, key):
    """流式解密生成器：逐块 yield 明文，块大小只跟封装时的设置走。

    v2 分块容器按每块自己头里记的密钥版本挑密钥，新旧版本可以混排；
    老的 v1 单块容器也能从这里解开。结构损坏、标签不符、块被调包挪位
    或尾巴被截，迭代时抛 AuthError，``chunk_index`` 记着出问题的块号。
    """
    head = _read_exact(src, V2_HEADER_LEN)
    if len(head) >= 4 and head[:4] == MAGIC_V2:
        if len(head) < V2_HEADER_LEN:
            raise AuthError("container is malformed: file header is truncated")
        yield from _unseal_v2(src, head, key)
    else:
        # 老 v1 容器（以及任何垃圾数据）交给整段入口处理。
        yield unseal(head + _read_all(src), key)


def _check_range(start, end):
    if not isinstance(start, int) or isinstance(start, bool) or start < 0:
        raise ValueError("start must be a non-negative int")
    if end is not None and (not isinstance(end, int) or isinstance(end, bool)):
        raise ValueError("end must be an int or None")
    if end is not None and end < start:
        raise ValueError("end (%d) is before start (%d)" % (end, start))


def rotate_file(path, new_version, keyring, start=0, end=None):
    """只把 [start, end) 这一段块换成 new_version 的密钥，其余原样搬运。

    end=None 表示一直换到末块。区间外的块帧逐字节照抄，区间内的块先验
    旧标签、解密，再用新密钥重封；salt 和块号不变，nonce 随新密钥重新
    派生。原子替换：先写同目录临时文件，全部成功才 os.replace。
    返回轮换的块数。只支持 v2 分块容器。
    """
    _check_range(start, end)
    selected_new = select_key(keyring, new_version)

    # 先开源文件（可能抛 OSError），成功了再占临时文件，避免 fd 泄漏。
    source = open(path, "rb")
    original_mode = os.fstat(source.fileno()).st_mode & 0o7777
    abs_path = os.path.abspath(path)
    directory = os.path.dirname(abs_path)
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=".rotate-", suffix=".tmp", dir=directory
    )
    rotated = 0
    try:
        with source, os.fdopen(tmp_fd, "wb") as dest:
            file_header = _read_exact(source, V2_HEADER_LEN)
            if len(file_header) < 4 or file_header[:4] != MAGIC_V2:
                raise FormatError(
                    "rotate_file only supports v2 streaming containers; "
                    "seal a v2 file with seal_stream first"
                )
            if len(file_header) < V2_HEADER_LEN:
                raise FormatError("v2 file header is truncated")
            _hdr, _default_version, salt, chunk_size = parse_v2_file_header(
                file_header
            )
            dest.write(file_header)

            enc_new = derive(selected_new, ENC_LABEL, salt)
            mac_new = derive(selected_new, MAC_LABEL, salt)
            old_subkeys = {}

            def old_keys(version, index):
                if version not in old_subkeys:
                    try:
                        old_key = select_key(keyring, version)
                    except UnknownKeyError as exc:
                        raise UnknownKeyError(
                            "chunk %d: %s" % (index, exc)
                        ) from exc
                    old_subkeys[version] = (
                        old_key,
                        derive(old_key, ENC_LABEL, salt),
                        derive(old_key, MAC_LABEL, salt),
                    )
                return old_subkeys[version]

            expected_index = 0
            while True:
                frame = _read_v2_frame(source, expected_index, chunk_size)
                if frame is None:
                    if expected_index == 0:
                        raise FormatError(
                            "container is truncated: no chunks at all"
                        )
                    raise AuthError(
                        "container is truncated: final chunk never appeared, "
                        "last seen chunk %d" % (expected_index - 1),
                        chunk_index=expected_index,
                    )
                chunk_header, index, flags, length, old_version, ciphertext, tag = (
                    frame
                )

                if index >= start and (end is None or index < end):
                    _old_key, enc_old, mac_old = old_keys(old_version, index)
                    if not verify_mac(
                        mac_old, file_header + chunk_header + ciphertext, tag
                    ):
                        raise AuthError(
                            "chunk %d tag mismatch, refusing to rotate a tampered "
                            "container" % index,
                            chunk_index=index,
                        )
                    plaintext = xor_stream(
                        enc_old, _chunk_nonce(_old_key, salt, index), ciphertext
                    )
                    _write_v2_chunk(
                        dest, file_header, index, flags,
                        selected_new, new_version, salt,
                        enc_new, mac_new, plaintext,
                    )
                    rotated += 1
                else:
                    # 区间外：整块原样搬运，一个字节都不改。
                    dest.write(chunk_header)
                    dest.write(ciphertext)
                    dest.write(tag)

                if flags & FLAG_FINAL:
                    if source.read(1):
                        raise FormatError(
                            "container carries extra bytes after final chunk %d"
                            % index
                        )
                    total_chunks = index + 1
                    break
                expected_index += 1
            if start >= total_chunks:
                raise ValueError(
                    "start (%d) is past the last chunk (%d)"
                    % (start, total_chunks - 1)
                )
            if end is not None and end > total_chunks:
                raise ValueError(
                    "end (%d) is past the last chunk (%d)"
                    % (end, total_chunks - 1)
                )
            os.fchmod(dest.fileno(), original_mode)
            os.replace(tmp_path, abs_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return rotated
