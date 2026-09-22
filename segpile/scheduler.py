"""后台压缩调度器：把合并拆成按预算执行的若干轮。

手动 compact_once 一次把整轮 IO 占死在设备上，写高峰时前台只能排队；
而且只挑最小的两段，滚出来的大段永远排不上。Scheduler 的做法：

- step() 推进一轮，一轮在设备上占的 IO 不超过 budget，占满就让路，
  前台写最多排一个 budget 的队；
- 只并在 (seq, sid) 序上相邻的两段，旧 key 才不会跳过中间段复活；
  选段按大小分层（每 segment_limit 一档），同层里等得久的先走；
  任何一段够格之后被插队 max_skips 次就强制优先，大段不会被小段
  无限挤下去；
- 合并全程占着输入段的锁，手动 compact_once 会绕开这些段；
- 合并先登记 journal 再动手，输出写进全新的段 id，最后一步才改段
  清单。进程死在半路，重新打开 Store 会认出没做完的合并：输出已
  落盘就前滚补完，没落盘就由新的 Scheduler 接着做，key 不丢不重。
"""

from .segment import merge_pairs
from .store import CompactReport


class _Task:
    """一轮进行中的合并，跨若干 step 推进。"""

    __slots__ = (
        "inputs", "out", "read_total", "read_done",
        "write_total", "write_done", "pairs", "units", "started",
    )

    def __init__(self, inputs, out, read_total, started):
        self.inputs = inputs
        self.out = out
        self.read_total = read_total
        self.read_done = 0
        self.write_total = 0
        self.write_done = 0
        self.pairs = None
        self.units = 0
        self.started = started


class Scheduler:
    """按预算分段执行合并的后台调度器。

    store: 要调度的 Store。
    budget: 一轮 step() 最多占多少 IO 单位，超了就让路。
    max_skips: 一段够格后最多被插队几次，到顶强制优先。
    """

    def __init__(self, store, budget=4, max_skips=10):
        if budget < 1:
            raise ValueError("budget must be at least 1")
        if max_skips < 0:
            raise ValueError("max_skips must be non-negative")
        self.store = store
        self.budget = budget
        self.max_skips = max_skips
        self.rounds = 0
        self.last_units = 0
        self._waits = {}
        self._skips = {}
        self._task = self._adopt()

    # ---------- 状态 ----------

    def _adopt(self):
        """认出 store 里没做完的合并，接着做。"""
        pending = self.store.pending_merge
        if pending is None:
            return None
        try:
            segs = [self.store.segment(sid) for sid in pending["inputs"]]
        except KeyError:
            self.store.abort_pending_merge()
            return None
        segs.sort(key=lambda s: s.order)
        return _Task(
            [s.sid for s in segs],
            dict(pending["output"]),
            sum(s.size for s in segs),
            self.store.device.now(),
        )

    def _eligible(self):
        """够格的段：非活动、没被锁、不在 journal 里。"""
        locked = self.store.locked_sids()
        active = self.store.active
        active_sid = None if active is None else active.sid
        return [
            s for s in self.store.segments()
            if s.sid != active_sid and s.sid not in locked
        ]

    def _prune(self):
        """清掉已经不在了的段的计分。"""
        live = {s.sid for s in self.store.segments()}
        for table in (self._waits, self._skips):
            for sid in list(table):
                if sid not in live:
                    del table[sid]

    def _age(self):
        """够格的段每轮都长一岁。"""
        for seg in self._eligible():
            self._waits[seg.sid] = self._waits.get(seg.sid, 0) + 1

    def wait_times(self):
        """当前每段已经等了多少轮，调试用。"""
        return {s.sid: self._waits.get(s.sid, 0) for s in self.store.segments()}

    # ---------- 选任务 ----------

    def _tier(self, seg):
        """段大小分层：每 segment_limit 一档。"""
        return seg.size // self.store.segment_limit

    def _pairs(self):
        """够格的相邻段对：非活动、没被锁、在 (seq, sid) 序上紧挨着。"""
        locked = self.store.locked_sids()
        active = self.store.active
        active_sid = None if active is None else active.sid
        segs = self.store.segments()
        pairs = []
        for left, right in zip(segs, segs[1:]):
            if active_sid in (left.sid, right.sid):
                continue
            if left.sid in locked or right.sid in locked:
                continue
            pairs.append((left, right))
        return pairs

    def _pick(self):
        """挑一对要并的相邻段：分层加等待打分，被插队到顶的强制优先。"""
        pairs = self._pairs()
        if not pairs:
            return None
        forced = [s for s in self._eligible() if self._skips.get(s.sid, 0) >= self.max_skips]
        if forced:
            top = max(self._skips[s.sid] for s in forced)
            pairs = [
                pair for pair in pairs
                if any(self._skips.get(s.sid, 0) >= top for s in pair)
            ]

        def key(pair):
            left, right = pair
            return (
                max(self._tier(left), self._tier(right)),
                -(self._waits.get(left.sid, 0) + self._waits.get(right.sid, 0)),
                left.seq,
                left.sid,
            )

        return min(pairs, key=key)

    # ---------- 推进 ----------

    def step(self):
        """推进一轮。有合并在这轮收尾就返回 CompactReport，否则 None。

        一轮在设备上占的 IO 不超过 budget，占满就让路给前台。
        """
        self.rounds += 1
        self._prune()
        self._age()
        device = self.store.device
        before = device.read_units + device.write_units
        spent = 0
        report = None
        if self._task is None:
            picked = self._pick()
            if picked is not None:
                self._task = self._begin(picked)
                spent += 1
        if self._task is not None:
            report = self._work(self._task, self.budget - spent)
        self.last_units = device.read_units + device.write_units - before
        return report

    def _begin(self, picked):
        """开一轮新合并：登记 journal，给没选上的段记一次插队。"""
        sids = [s.sid for s in picked]
        inputs, out = self.store.begin_merge(sids, owner=self)
        read_total = sum(self.store.segment(sid).size for sid in inputs)
        task = _Task(inputs, out, read_total, self.store.device.now())
        task.units += 1
        for seg in self._eligible():
            self._skips[seg.sid] = self._skips.get(seg.sid, 0) + 1
        for sid in sids:
            self._skips.pop(sid, None)
            self._waits.pop(sid, None)
        return task

    def _work(self, task, budget_left):
        """按剩下的预算推进合并：读、写、commit。"""
        device = self.store.device
        if task.pairs is None and budget_left > 0:
            chunk = min(budget_left, task.read_total - task.read_done)
            if chunk > 0:
                device.reserve("read", chunk)
                task.read_done += chunk
                task.units += chunk
                budget_left -= chunk
            if task.read_done >= task.read_total:
                blobs = [self.store.segment(sid).as_pairs() for sid in task.inputs]
                task.pairs = merge_pairs(blobs)
                task.write_total = len(task.pairs)
        if task.pairs is not None and task.write_done < task.write_total and budget_left > 0:
            chunk = min(budget_left, task.write_total - task.write_done)
            device.reserve("write", chunk)
            task.write_done += chunk
            task.units += chunk
            budget_left -= chunk
            if task.write_done >= task.write_total:
                self.store.write_merge_output(task.out, task.pairs)
        if (
            task.pairs is not None
            and task.write_done >= task.write_total
            and budget_left >= 1
        ):
            end = self.store.commit_merge(task.inputs, task.out, owner=self)
            task.units += 1
            self._task = None
            return CompactReport(
                task.inputs, task.out["sid"], task.out["seq"],
                task.units, end - task.started,
            )
        return None

    def __repr__(self):
        return "Scheduler(budget=%d, rounds=%d, task=%s)" % (
            self.budget, self.rounds, "active" if self._task else "idle")
