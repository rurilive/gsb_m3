"""内容寻址的盘上布局与原子落盘原语。

布局（均相对 store root）：

    objects/<sha256 前两位>/<sha256>.blob   内容对象，一字节一份
    names.idx                               名字 -> sha256 的 JSON 索引
    gc-ledger.json                          回收失败的待重试账本

所有落盘都走 "先写 .bvtmp-* 临时文件，再 os.replace 原子改名"。
临时文件统一带 .bvtmp- 前缀，store 打开时只清扫这种自己的半成品。
"""

import hashlib
import json
import os
import re
import time
from contextlib import contextmanager

try:
    import fcntl
except ImportError:  # 非 POSIX 平台退化为无跨进程锁
    fcntl = None

from blobvault.errors import BlobError
from blobvault.keys import OBJECTS_DIR, OBJECT_SUFFIX

NAMES_INDEX = "names.idx"
GC_LEDGER = "gc-ledger.json"
TMP_PREFIX = ".bvtmp-"
TMP_SUFFIX = ".part"
# 临时文件的最长在途时间：超过这么多秒的遗留半成品才允许启动清扫；
# 正常写入（含 fsync）远在此之内，避免扫掉别的活进程刚建的临时文件。
TMP_STALE_SECONDS = 600

TMP_NAME_RE = re.compile(
    r"^" + re.escape(TMP_PREFIX)
    + r"(?P<pid>\d+)-\d+-(?P<ts>\d+)" + re.escape(TMP_SUFFIX) + r"$"
)

HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def digest_of(data):
    """返回 data 的 sha256 十六进制摘要。"""
    return hashlib.sha256(data).hexdigest()


def shard_of_digest(digest):
    """取对象所在的两位分片目录名。"""
    return digest[:2]


def object_relpath(digest):
    """返回对象相对 root 的路径，形如 objects/ab/ab..ff.blob。"""
    return "%s/%s/%s%s" % (OBJECTS_DIR, digest[:2], digest, OBJECT_SUFFIX)


def object_path(root, digest):
    """返回对象的绝对路径。"""
    return os.path.join(root, object_relpath(digest))


def iter_blob_files(root):
    """遍历 objects 目录下名字为合法 64 位 hex 的对象文件。

    产出 (digest, 绝对路径, 字节数)；后缀不符或文件名不是 hex 的外来
    文件一律跳过，绝不当成本库对象处理。
    """
    base = os.path.join(root, OBJECTS_DIR)
    for dirpath, _dirnames, filenames in os.walk(base):
        for fn in filenames:
            if not fn.endswith(OBJECT_SUFFIX):
                continue
            digest = fn[: -len(OBJECT_SUFFIX)]
            if not HEX_RE.match(digest):
                continue
            ap = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(ap)
            except OSError:
                continue
            yield digest, ap, size


def verify_object(path, expected_digest):
    """校验盘上对象：读取并比对 sha256。

    对象缺失/不是普通文件/摘要对不上都抛 BlobError（调用方按需转成
    ObjectCorrupted），保证坏字节绝不会被当成正确内容交出去。
    """
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError as exc:
        raise BlobError("对象不可读: %s (%s)" % (expected_digest, exc))
    actual = h.hexdigest()
    if actual != expected_digest:
        raise BlobError(
            "对象校验失败: 期望 %s 实得 %s" % (expected_digest, actual)
        )


def read_verified_object(path, expected_digest):
    """一次性读出对象并在同一份字节上校验摘要，通过才返回内容。

    避免 "先校验、再读取" 两次读之间被掉包的 TOCTOU：交出去的字节
    就是摘要算过的那一份，坏字节不可能漏网。
    """
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise BlobError("对象不可读: %s (%s)" % (expected_digest, exc))
    actual = digest_of(data)
    if actual != expected_digest:
        raise BlobError(
            "对象校验失败: 期望 %s 实得 %s" % (expected_digest, actual)
        )
    return data


def atomic_write_bytes(final_path, data):
    """先写同目录临时文件再原子改名；临时名按进程/线程带随机后缀。"""
    directory = os.path.dirname(final_path)
    os.makedirs(directory, exist_ok=True)
    # 临时名绝不能带目标文件名：同目录两个写者的临时名一旦包含彼此的
    # 目标名，启动清扫/异常清理会误删别人的半成品。名里编码 pid、
    # 随机数与创建时间戳，供启动清扫区分活进程与崩溃遗留。
    tmp_name = "%s%d-%d-%d%s" % (
        TMP_PREFIX,
        os.getpid(),
        int.from_bytes(os.urandom(8), "big"),
        int(time.time()),
        TMP_SUFFIX,
    )
    tmp_path = os.path.join(directory, tmp_name)
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, final_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def sweep_tmp_files(root):
    """扫掉 root 下本库遗留的临时半成品。

    只删名以 .bvtmp- 开头、以 .part 结尾，且确认是崩溃遗留的文件
    （任意层级）：编码 pid 仍活着的不删，未超过在途宽限期的不删。
    目录里其他东西一律不碰；删除本身尽力而为。
    """
    removed = 0
    now = time.time()
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if not (fn.startswith(TMP_PREFIX) and fn.endswith(TMP_SUFFIX)):
                continue
            full = os.path.join(dirpath, fn)
            match = TMP_NAME_RE.match(fn)
            if match is not None:
                pid = int(match.group("pid"))
                created = int(match.group("ts"))
                if _pid_alive(pid):
                    continue
                if now - created < TMP_STALE_SECONDS:
                    continue
            else:
                # 旧格式/无法解析的临时名：只按修改时间宽限判断。
                try:
                    age = now - os.path.getmtime(full)
                except OSError:
                    continue
                if age < TMP_STALE_SECONDS:
                    continue
            try:
                os.unlink(full)
                removed += 1
            except OSError:
                pass
    return removed


def _pid_alive(pid):
    """pid 对应进程是否仍在运行（无法判断时保守视为活着）。"""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def load_names(root):
    """读名字索引，返回 {name: digest}；索引不存在时为空映射。"""
    path = os.path.join(root, NAMES_INDEX)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise BlobError("名字索引不可读: %s" % (exc,))
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BlobError("名字索引损坏: %s" % (exc,))
    if not isinstance(parsed, dict) or not all(
        isinstance(name, str)
        and isinstance(digest, str)
        and HEX_RE.match(digest)
        for name, digest in parsed.items()
    ):
        raise BlobError("名字索引格式非法")
    return dict(parsed)


def save_names(root, names):
    """原子重写名字索引。"""
    data = json.dumps(names, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    atomic_write_bytes(os.path.join(root, NAMES_INDEX), data.encode("utf-8"))


def load_ledger(root):
    """读回收失败账本，返回 {digest: {"attempts": n, "error": str}}。"""
    path = os.path.join(root, GC_LEDGER)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise BlobError("回收账本不可读: %s" % (exc,))
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BlobError("回收账本损坏: %s" % (exc,))
    if not isinstance(parsed, dict) or not all(
        isinstance(digest, str)
        and isinstance(entry, dict)
        and isinstance(entry.get("attempts"), int)
        and isinstance(entry.get("error", ""), str)
        for digest, entry in parsed.items()
    ):
        raise BlobError("回收账本格式非法")
    return dict(parsed)


def save_ledger(root, ledger):
    """原子重写回收失败账本。"""
    data = json.dumps(
        ledger, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    atomic_write_bytes(os.path.join(root, GC_LEDGER), data.encode("utf-8"))


def remove_ledger_if_empty(root, ledger):
    """账本为空时删掉账本文件；删除失败不影响主流程。"""
    if ledger:
        save_ledger(root, ledger)
        return
    try:
        os.unlink(os.path.join(root, GC_LEDGER))
    except FileNotFoundError:
        pass
    except OSError:
        pass


@contextmanager
def flock_root(root):
    """对 root 目录本身加进程级咨询锁（flock 随 fd 生命周期）。

    同一 root 上的多个 ObjectStore 进程借此串行化写变更；fd 在 store
    生命周期内常驻，构造时即加锁。POSIX 之外的平台静默退化。
    """
    fd = None
    if fcntl is not None and os.path.isdir(root):
        fd = os.open(root, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError:
            os.close(fd)
            fd = None
    try:
        yield
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
