"""内容寻址的二进制对象库。

盘上分三区（详见 blobvault.keys）：
- objects 按 sha256 摘要存放对象本体，相同字节全局只有一份；
- index 下每个名字是一个 .ref 小文件，内容是它指向的对象摘要，
  删名字只删引用，对象本体等 gc() 回收；
- gc/pending 是回收欠账本，删不掉的对象记账，下次 gc 重试。

落盘一律先写同目录 .bvtmp 临时文件再 os.replace 原子改名；构造时
扫掉自己的半成品临时文件，外来文件一律不碰。get 时重新算摘要比对，
对象被改坏或丢失一律抛 CorruptObject，绝不把错字节交给调用方。
进程内一把 RLock 串行化所有写操作与回收，root 不存在时首次写自动建。
"""

import os
import threading
import uuid

from blobvault.errors import CorruptObject, ObjectNotFound
from blobvault.keys import (
    digest_of,
    is_digest,
    ledger_relpath,
    object_relpath,
    parse_digest,
    ref_relpath,
    tmp_relpath,
    validate_key,
)
from blobvault.maint import iter_objects, iter_refs, iter_tmp_files


class ObjectStore:
    """内容寻址的名字到字节映射，所有数据放在 root 目录下。"""

    def __init__(self, root):
        self.root = os.fspath(root)
        self._lock = threading.RLock()
        self._sweep_temps()

    # ---- 路径与落盘原语 -------------------------------------------------

    def _abs(self, relpath):
        return os.path.join(self.root, relpath.replace("/", os.sep))

    @staticmethod
    def _fsync_dir(path):
        """fsync 目录让改名落盘；不支持 fsync 的平台上静默跳过。"""
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        except OSError:
            pass
        finally:
            os.close(fd)

    def _atomic_write(self, relpath, data):
        """同目录临时文件 + fsync + os.replace，绝不留半截正式文件。"""
        final = self._abs(relpath)
        tmp = self._abs(tmp_relpath(relpath, uuid.uuid4().hex))
        os.makedirs(os.path.dirname(final), exist_ok=True)
        try:
            with open(tmp, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, final)
            self._fsync_dir(os.path.dirname(final))
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
        return final

    def _sweep_temps(self):
        """重开库时清掉自己的半成品临时文件，只认 .bvtmp，不碰别的。"""
        for ap in iter_tmp_files(self.root):
            with self._lock:
                try:
                    os.remove(ap)
                except FileNotFoundError:
                    pass

    # ---- 基本存取 -------------------------------------------------------

    def put(self, name, data):
        """把 data 绑给名字 name，返回对象本体相对 root 的落盘路径。

        data 只收字节串，传 str 直接 TypeError；同名重复写即换引用。
        相同字节全局只落一份对象，名字只是指向摘要的引用。
        """
        if isinstance(data, str) or not isinstance(
            data, (bytes, bytearray, memoryview)
        ):
            raise TypeError("put 只收字节串，收到 %s" % type(data).__name__)
        validate_key(name)
        payload = bytes(data)
        digest = digest_of(payload)
        obj_rel = object_relpath(digest)
        ref_rel = ref_relpath(name)
        with self._lock:
            obj_path = self._abs(obj_rel)
            if not os.path.exists(obj_path):
                self._atomic_write(obj_rel, payload)
            self._atomic_write(ref_rel, digest.encode("ascii"))
        return obj_rel

    def get(self, name):
        """读回 name 的字节；名字不存在抛 ObjectNotFound，对象对不上抛
        CorruptObject。引用与对象都重新校验，改坏的字节绝不交出去。"""
        validate_key(name)
        with self._lock:
            ref_path = self._abs(ref_relpath(name))
            try:
                with open(ref_path, "rb") as fh:
                    raw = fh.read()
            except (FileNotFoundError, IsADirectoryError):
                raise ObjectNotFound(name) from None
            try:
                digest = parse_digest(raw.decode("ascii").strip())
            except (ValueError, UnicodeDecodeError):
                raise CorruptObject(
                    "名字 %r 的引用已损坏: %r" % (name, raw[:64])
                ) from None
            obj_path = self._abs(object_relpath(digest))
            try:
                with open(obj_path, "rb") as fh:
                    data = fh.read()
            except (FileNotFoundError, IsADirectoryError):
                raise CorruptObject(
                    "名字 %r 引用的对象 %s 已丢失" % (name, digest)
                ) from None
            if digest_of(data) != digest:
                raise CorruptObject(
                    "名字 %r 读出的内容与摘要 %s 不符" % (name, digest)
                )
            return data

    def delete(self, name):
        """删掉名字 name（只减引用，不动对象本体），返回是否删到了。"""
        validate_key(name)
        with self._lock:
            ref_path = self._abs(ref_relpath(name))
            try:
                os.remove(ref_path)
                return True
            except (FileNotFoundError, IsADirectoryError):
                return False

    def list(self):
        """返回全部名字，升序；空库返回空列表。"""
        return sorted(name for name, _ap in iter_refs(self.root))

    # ---- 回收与统计 -----------------------------------------------------

    @staticmethod
    def _read_ledger(ap):
        """读回收欠账本，每行一个摘要；坏行/重复行忽略，文件不在返回空。"""
        try:
            with open(ap, "rb") as fh:
                lines = fh.read().decode("ascii").splitlines()
        except (FileNotFoundError, IsADirectoryError):
            return []
        except (OSError, UnicodeDecodeError):
            return []
        owed, seen = [], set()
        for line in lines:
            line = line.strip()
            if is_digest(line) and line not in seen:
                seen.add(line)
                owed.append(line)
        return owed

    def _live_digests(self):
        """汇总所有名字引用指向的摘要；引用损坏时抛 CorruptObject，
        此时无法排除任何对象，gc 宁可不收也不误删内容。"""
        live, bad = set(), []
        for name, ref_ap in iter_refs(self.root):
            try:
                with open(ref_ap, "rb") as fh:
                    digest = parse_digest(fh.read().decode("ascii").strip())
            except (OSError, ValueError, UnicodeDecodeError):
                bad.append(name)
                continue
            live.add(digest)
        if bad:
            raise CorruptObject("引用损坏的名字: %s" % ", ".join(sorted(bad)))
        return live

    def gc(self):
        """回收没有任何名字引用的对象。

        删除失败的对象记入 gc/pending 欠账本，下次 gc 先重试欠账；
        欠账对象若被重新指回则视为存活、当场销账。返回 dict：
        removed 本轮删掉的对象数，bytes 释放字节数，retry 其中属于
        历史欠账本轮才删掉的个数，pending 仍删不掉继续记账的个数。
        """
        with self._lock:
            live = self._live_digests()
            ledger_ap = self._abs(ledger_relpath())
            owed = self._read_ledger(ledger_ap)

            candidates = set(owed)
            for digest, _ap in iter_objects(self.root):
                if digest not in live:
                    candidates.add(digest)

            removed, retried, failed = {}, 0, []
            for digest in sorted(candidates):
                if digest in live:
                    continue  # 又有名字指回来了：历史欠账当场勾掉
                ap = self._abs(object_relpath(digest))
                try:
                    size = os.path.getsize(ap)
                    os.remove(ap)
                except FileNotFoundError:
                    continue  # 对象已不在，欠账同样勾掉
                except OSError:
                    failed.append(digest)
                    continue
                removed[digest] = size
                if digest in owed:
                    retried += 1

            if failed:
                body = "".join(d + "\n" for d in sorted(set(failed)))
                self._atomic_write(ledger_relpath(), body.encode("ascii"))
            else:
                try:
                    os.remove(ledger_ap)
                except FileNotFoundError:
                    pass

            return {
                "removed": len(removed),
                "bytes": sum(removed.values()),
                "retry": retried,
                "pending": len(failed),
            }

    def stats(self):
        """返回对象数、名字数与对象本体占用字节：
        {"objects", "names", "bytes"}，只统计 blobvault 自己的正式文件。"""
        with self._lock:
            objects = list(iter_objects(self.root))
            names = list(iter_refs(self.root))
            total = 0
            for _digest, ap in objects:
                try:
                    total += os.path.getsize(ap)
                except OSError:
                    pass
            return {"objects": len(objects), "names": len(names), "bytes": total}
