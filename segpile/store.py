"""分段存储引擎。

写入先进活动段；活动段写满 segment_limit 个 key 就滚出一段新的，
老的那段封住不动。查询从最新往旧扫，同一个 key 取最新的段里的值。

压缩目前只有手动入口 compact_once()：挑当前最小的相邻两段并成一段，
一次调用少一段。并出来的结果沿用最新输入那一段的 sid 和 seq，
段与段之间的新旧关系不会因为合并而变化。注意只有相邻两段能并：
隔着别的段硬并，旧 key 会跳过中间段里的新值复活。

后台调度（见 scheduler.py）走的是另一套可崩溃恢复的合并：先往 meta
登记 pending_merge 这条 journal，输出写进一个全新的段 id，最后一步
才改段清单（commit）。进程死在半路的话，重新打开 Store 会认出这条
journal：输出已落盘就前滚补完，没落盘就原样留给新的 Scheduler 接着
做，key 不丢不重。合并期间输入段持有锁，compact_once 会绕开它们。

落盘都从 device 走账：前台写读走 charge，同步等设备空出来；压缩把
整轮 IO 一次 reserve 在设备上，前台再来的请求就得排队等。打开 Store
时把段读回内存，恢复动作不计账。

meta 文档存在后端里，记 next_sid、next_seq、活动段 id 和段清单；
每次滚段、合并都会重写它。重新 new 一个 Store 读同一份后端，
就是进程重启后的样子。
"""

import copy

from .backend import MemoryBackend
from .device import SimDevice
from .segment import Segment, merge_pairs

DEFAULT_SEGMENT_LIMIT = 8


class CompactReport:
    """一次合并的账。"""

    __slots__ = ("inputs", "sid", "seq", "units", "elapsed")

    def __init__(self, inputs, sid, seq, units, elapsed):
        self.inputs = tuple(inputs)
        self.sid = sid
        self.seq = seq
        self.units = units
        self.elapsed = elapsed

    def __repr__(self):
        return "CompactReport(inputs=%r, sid=%r, units=%d, elapsed=%.1f)" % (
            self.inputs, self.sid, self.units, self.elapsed)


class Store:
    """分段存储。

    backend: 段落后端，默认开一个进程内的 MemoryBackend。
    device: IO 设备兼模型时钟，默认开一个 SimDevice。
    segment_limit: 活动段装多少个 key 之后滚新段。
    """

    def __init__(self, backend=None, device=None, segment_limit=DEFAULT_SEGMENT_LIMIT):
        if segment_limit < 1:
            raise ValueError("segment_limit must be positive")
        self.backend = MemoryBackend() if backend is None else backend
        self.device = SimDevice() if device is None else device
        self.segment_limit = segment_limit
        self._segments = {}
        self._claims = {}
        self._meta = self._load_meta()

    # ---------- 打开与落盘 ----------

    def _load_meta(self):
        """把后端里的 meta 和段读进来，没有就开一份空的。

        带着 pending_merge 打开说明上次合并做到一半：输出段已落盘就
        前滚补完（换段清单、清 journal、删输入段），没落盘就原样保留
        journal，等 Scheduler 认领接着做。恢复动作不计账。
        """
        meta = self.backend.load_meta()
        if meta is None:
            meta = {"next_sid": 0, "next_seq": 0, "active": None,
                    "segments": [], "pending_merge": None}
        pending = meta.get("pending_merge")
        if pending is not None:
            meta = self._recover(meta, pending)
        self._segments = {}
        for row in meta["segments"]:
            seg = Segment(
                row["sid"],
                self.backend.read_segment(row["sid"]),
                seq=row["seq"],
                created=row["created"],
            )
            self._segments[seg.sid] = seg
        self._drop_orphans(meta)
        return meta

    def _recover(self, meta, pending):
        """处理没做完的合并，返回恢复后的 meta。"""
        out = pending["output"]
        if out["sid"] in self.backend.segment_ids():
            inputs = set(pending["inputs"])
            meta["segments"] = [
                row for row in meta["segments"] if row["sid"] not in inputs
            ] + [dict(out)]
            for sid in inputs:
                self.backend.drop_segment(sid)
            meta["pending_merge"] = None
            self.backend.save_meta(meta)
        return meta

    def _drop_orphans(self, meta):
        """清掉不在段清单里的孤儿 blob（比如 commit 后没来得及删的输入段）。"""
        keep = {row["sid"] for row in meta["segments"]}
        for sid in self.backend.segment_ids():
            if sid not in keep:
                self.backend.drop_segment(sid)

    def _save_meta(self, background=False):
        """把段清单写回 meta，返回这次写盘的完成时刻。

        background=True 走 reserve，占住设备但不推进前台时钟。
        """
        rows = [
            {"sid": seg.sid, "seq": seg.seq, "created": seg.created}
            for seg in self.segments()
        ]
        self._meta["segments"] = rows
        self.backend.save_meta(self._meta)
        if background:
            return self.device.reserve("write", 1)
        return self.device.charge("write", 1)

    # ---------- 视图 ----------

    def segments(self):
        """现存的所有段，按 (seq, sid) 升序，越靠后越新。"""
        return sorted(self._segments.values(), key=lambda s: s.order)

    @property
    def active(self):
        """当前可写的活动段，可能还没有。"""
        sid = self._meta["active"]
        return None if sid is None else self._segments.get(sid)

    def snapshot(self):
        """当前全量视图，最新的值赢。调试与对拍用，不记 IO。"""
        values = {}
        for seg in self.segments():
            values.update(dict(seg.items))
        return values

    def segment(self, sid):
        """按 id 取段，不存在抛 KeyError。"""
        return self._segments[sid]

    # ---------- 段锁 ----------

    def claim_segments(self, sids, owner):
        """给若干段上锁，已被别人占住或带着 journal 的段会拒绝。"""
        journaled = self.locked_sids() - set(self._claims)
        for sid in sids:
            if sid in journaled:
                raise RuntimeError("segment %r is busy in a journaled merge" % (sid,))
            holder = self._claims.get(sid)
            if holder is not None and holder is not owner:
                raise RuntimeError("segment %r already claimed" % (sid,))
        for sid in sids:
            self._claims[sid] = owner

    def release_segments(self, sids, owner):
        """解锁，只解自己占住的。"""
        for sid in sids:
            if self._claims.get(sid) is owner:
                del self._claims[sid]

    def locked_sids(self):
        """当前不许动的段：被占住的加上 journal 里没做完的。"""
        locked = set(self._claims)
        pending = self._meta.get("pending_merge")
        if pending is not None:
            locked.update(pending["inputs"])
            locked.add(pending["output"]["sid"])
        return locked

    # ---------- 读写 ----------

    def put(self, key, value):
        """写一条数据进活动段，返回这次前台写的耗时。"""
        if key is None:
            raise ValueError("key must not be None")
        started = self.device.now()
        active = self.active
        if active is None or active.size >= self.segment_limit:
            active = self._rotate()
        pairs = [(k, v) for k, v in active.items if k != key]
        pairs.append((key, value))
        seg = Segment(active.sid, pairs, seq=active.seq, created=active.created)
        self._segments[seg.sid] = seg
        self.backend.write_segment(seg.sid, seg.as_pairs())
        end = self.device.charge("write", 1)
        return end - started

    def get(self, key):
        """查一个 key，取最新的段里的值，查不到返回 None。"""
        self.device.charge("read", 1)
        for seg in reversed(self.segments()):
            if key in seg:
                return seg.lookup(key)
        return None

    def _rotate(self):
        """封住当前活动段，开一段新的。"""
        sid = self._meta["next_sid"]
        seq = self._meta["next_seq"]
        self._meta["next_sid"] = sid + 1
        self._meta["next_seq"] = seq + 1
        seg = Segment(sid, [], seq=seq, created=self.device.now())
        self._segments[sid] = seg
        self.backend.write_segment(sid, [])
        self.device.charge("write", 1)
        self._meta["active"] = sid
        self._save_meta()
        return seg

    # ---------- 压缩 ----------

    def compact_once(self):
        """手动压缩一轮：挑最小的相邻两段并成一段，不够就返回 None。

        整轮合并的 IO 一次占住设备，前台写要等它让出来。
        """
        picked = self._candidates()
        if picked is None:
            return None
        return self._merge(picked)

    def _candidates(self):
        """够格的相邻段对里最值得并的一对。

        相邻指在 (seq, sid) 序上紧挨着；活动段不算，被后台合并锁住的
        段也不算。段对按 (较大 size, size 之和, seq, sid) 升序挑最小的。
        """
        active = self._meta["active"]
        locked = self.locked_sids()
        best = None
        segs = self.segments()
        for left, right in zip(segs, segs[1:]):
            if active in (left.sid, right.sid):
                continue
            if left.sid in locked or right.sid in locked:
                continue
            key = (max(left.size, right.size), left.size + right.size,
                   left.seq, left.sid)
            if best is None or key < best[0]:
                best = (key, (left, right))
        return None if best is None else list(best[1])

    def _merge(self, picked):
        """把这几段并成一段，结果顶掉最新输入那一段的身份。

        整轮 IO 一次 reserve 在设备上：reads 的单位数是输入段之和，写是
        结果段的大小，另外还有一个单位写 meta。占设备不推进前台时钟，
        前台写撞上这段占用就得排队。
        """
        started = self.device.now()
        inputs = sorted(picked, key=lambda s: s.order)
        newest = inputs[-1]
        read_units = sum(s.size for s in inputs)
        self.device.reserve("read", read_units)
        blobs = [self.backend.read_segment(s.sid) for s in inputs]
        pairs = merge_pairs(blobs)

        self.device.reserve("write", len(pairs))
        self.backend.write_segment(newest.sid, pairs)
        for seg in inputs[:-1]:
            self.backend.drop_segment(seg.sid)
            del self._segments[seg.sid]
        merged = Segment(newest.sid, pairs, seq=newest.seq, created=newest.created)
        self._segments[merged.sid] = merged
        end = self._save_meta(background=True)
        units = read_units + len(pairs) + 1
        return CompactReport([s.sid for s in inputs], merged.sid, merged.seq, units, end - started)

    # ---------- 可调度的合并（Scheduler 专用） ----------

    @property
    def pending_merge(self):
        """没做完的合并 journal，没有就是 None。Scheduler 靠它接着做。"""
        pending = self._meta.get("pending_merge")
        return None if pending is None else copy.deepcopy(pending)

    def begin_merge(self, sids, owner=None):
        """登记一轮合并：上锁、写 journal，返回 (输入 sid 列表, 输出段行)。

        输出段用全新的 sid，seq 沿用最新输入那一段，段间新旧关系不变。
        journal 落盘之前不动任何 blob，崩在这里等于没做过。
        """
        if len(sids) < 2:
            raise ValueError("need at least two segments to merge")
        active = self._meta["active"]
        locked = self.locked_sids()
        picked = []
        for sid in sids:
            seg = self._segments.get(sid)
            if seg is None:
                raise KeyError(sid)
            if sid == active:
                raise ValueError("active segment %r cannot be merged" % (sid,))
            if sid in locked:
                raise RuntimeError("segment %r is locked" % (sid,))
            picked.append(seg)
        if owner is not None:
            self.claim_segments(sids, owner)
        inputs = sorted(picked, key=lambda s: s.order)
        newest = inputs[-1]
        out = {"sid": self._meta["next_sid"], "seq": newest.seq,
               "created": newest.created}
        self._meta["next_sid"] += 1
        self._meta["pending_merge"] = {
            "inputs": [s.sid for s in inputs],
            "output": out,
        }
        self._save_meta(background=True)
        return [s.sid for s in inputs], out

    def write_merge_output(self, out, pairs):
        """把归并结果写进输出段。只占 blob，不进段清单，崩了是个孤儿。"""
        self.backend.write_segment(out["sid"], pairs)

    def commit_merge(self, input_sids, out, owner=None):
        """收尾一轮合并：换段清单、清 journal、删输入段，返回完成时刻。

        这是合并的 commit 点：meta 落盘之后这轮合并就生效了，之后崩了
        重新打开也认这个清单。
        """
        pending = self._meta.get("pending_merge")
        if pending is None or pending["output"]["sid"] != out["sid"]:
            raise RuntimeError("no matching pending merge for sid %r" % (out["sid"],))
        merged = Segment(
            out["sid"],
            self.backend.read_segment(out["sid"]),
            seq=out["seq"],
            created=out["created"],
        )
        for sid in input_sids:
            self._segments.pop(sid, None)
            self.backend.drop_segment(sid)
        self._segments[merged.sid] = merged
        self._meta["pending_merge"] = None
        end = self._save_meta(background=True)
        if owner is not None:
            self.release_segments(input_sids, owner)
        return end

    def abort_pending_merge(self):
        """作废没做完的合并：清 journal、删可能存在的输出 blob。

        输入段原样还在，key 不丢。只在没有 Scheduler 接管时调用。
        """
        pending = self._meta.get("pending_merge")
        if pending is None:
            return None
        self.backend.drop_segment(pending["output"]["sid"])
        self._meta["pending_merge"] = None
        return self._save_meta(background=True)

    def __repr__(self):
        return "Store(segments=%d, active=%r, limit=%d)" % (
            len(self._segments), self._meta["active"], self.segment_limit)
