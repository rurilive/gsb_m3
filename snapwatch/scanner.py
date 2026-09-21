"""快照扫描：走一遍目录树，只记元数据，内容摘要按需现算。"""

import hashlib
import os

from .fs import SysFS


class Entry:
    """快照里的一个节点，路径是相对 root 的 posix 串。"""

    __slots__ = ("path", "is_dir", "mtime_ns", "size", "inode",
                 "_abs", "_fs", "_digest")

    def __init__(self, path, is_dir, mtime_ns, size, inode,
                 abs_path=None, fs=None, digest=None):
        self.path, self.is_dir = path, is_dir
        self.mtime_ns, self.size = mtime_ns, size
        self.inode, self._abs = inode, abs_path
        self._fs, self._digest = fs, digest

    @property
    def digest(self):
        """文件内容的 sha256；快照里没算过就现读一次，目录恒为 None。"""
        if self.is_dir:
            return None
        if self._digest is None:
            data = self._fs.read_bytes(self._abs)
            self._digest = hashlib.sha256(data).hexdigest()
        return self._digest

    def __repr__(self):
        return "Entry(%r, is_dir=%r, size=%r)" % (
            self.path, self.is_dir, self.size)


class Snapshot:
    """一次扫描的结果。"""

    def __init__(self, root):
        self.root = root
        self.entries = {}
        self.unreachable = set()

    def mark_unreachable(self, path):
        """rel 这个目录本轮 stat 得到但读不出名字，子树状态未知。"""
        self.unreachable.add(path)

    def entry(self, path):
        """相对路径对应的 Entry，没有这个路径时抛 KeyError。"""
        return self.entries[path]

    def paths(self):
        return sorted(self.entries)

    def __len__(self):
        return len(self.entries)

    def is_unreachable(self, path):
        """path 是否挂在本轮某个读不出来的目录子树下面。"""
        rel = path
        while True:
            if rel in self.unreachable:
                return True
            if not rel:
                return False
            rel = rel.rsplit("/", 1)[0] if "/" in rel else ""


class PollScanner:
    """把 root 下的目录树扫成 Snapshot。"""

    def __init__(self, fs, root):
        self.fs = fs
        self.root = root

    def _abs(self, rel):
        return os.path.join(self.root, rel) if rel else self.root

    def scan(self):
        snapshot = Snapshot(self.root)
        try:
            root_names = self.fs.scandir(self.root)
        except OSError:
            snapshot.mark_unreachable("")
            return snapshot
        for name in sorted(root_names):
            self._walk(name, snapshot)
        return snapshot

    def _walk(self, rel, snapshot):
        try:
            info = self.fs.stat(self._abs(rel))
        except OSError:
            return
        snapshot.entries[rel] = Entry(
            rel, info.is_dir, info.mtime_ns, info.size, info.inode,
            abs_path=self._abs(rel), fs=self.fs)
        if not info.is_dir:
            return
        try:
            names = self.fs.scandir(self._abs(rel))
        except OSError:
            snapshot.mark_unreachable(rel)
            return
        for name in names:
            child = name if not rel else rel + "/" + name
            self._walk(child, snapshot)
