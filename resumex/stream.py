"""把上游的记录按批推给下游。

来源与下游都是注入的内存对象，用来顶替真实 IO。搬运器逐批取数、
推送，并把进度记在内存里：推了多少条、走到哪个序号、推了几批。

断点续传：WatermarkStore 把确认水位追加落盘，重启先认水位，来源
按水位之后取数；DedupSink 把序号不超过水位的重复、乱序记录一律
丢弃并计数。buffer_size 给出有界缓冲，缓冲满即停止从来源取数，
阻塞次数计入进度。
"""

import os
import threading
import time
import zlib


class Record:
    """一条待搬运的记录。

    seq: 记录序号，从 1 开始，比较水位时以它为准。
    payload: 载荷，原样透传给下游。
    """

    __slots__ = ("seq", "payload")

    def __init__(self, seq, payload):
        self.seq = seq
        self.payload = payload

    def __repr__(self):
        return "Record(seq=%r, payload=%r)" % (self.seq, self.payload)

    def __eq__(self, other):
        if not isinstance(other, Record):
            return NotImplemented
        return self.seq == other.seq and self.payload == other.payload


class MemorySource:
    """内存来源，模拟一个能按序号区间查询的上游。

    records: 可迭代的 (seq, payload) 对，序号须严格递增。
    """

    def __init__(self, records=()):
        self._entries = []  # [(seq, payload), ...]
        for seq, payload in records:
            self.append(seq, payload)

    def append(self, seq, payload):
        """追加一条记录，序号必须大于已有的最大序号。"""
        if self._entries and seq <= self._entries[-1][0]:
            raise ValueError("seq must be strictly increasing")
        self._entries.append((seq, payload))

    def fetch(self, after_seq, limit):
        """取序号大于 after_seq 的至多 limit 条，按序号递增返回记录列表。"""
        if limit < 1:
            raise ValueError("limit must be >= 1")
        out = []
        for seq, payload in self._entries:
            if seq > after_seq:
                out.append(Record(seq, payload))
                if len(out) == limit:
                    break
        return out

    @property
    def latest_seq(self):
        """已有记录的最大序号，空时返回 0。"""
        return self._entries[-1][0] if self._entries else 0

    def __len__(self):
        return len(self._entries)


class MemorySink:
    """内存下游，模拟接收推送的外部系统。

    收到的记录按到达顺序留档，watermark 是收到的最大序号。
    """

    def __init__(self):
        self._received = []
        self._watermark = 0
        self._batches = 0

    def push(self, records):
        """接收一批记录，返回接收后的水位。"""
        self._batches += 1
        for record in records:
            self._received.append(record)
            if record.seq > self._watermark:
                self._watermark = record.seq
        return self._watermark

    @property
    def watermark(self):
        return self._watermark

    def received(self):
        """按到达顺序返回已收到记录的快照，新列表，调用方随便改。"""
        return list(self._received)

    def stats(self):
        """计数快照，返回独立 dict。"""
        return {
            "batches": self._batches,
            "received": len(self._received),
            "watermark": self._watermark,
        }


class DedupSink:
    """认水位的内存下游。

    序号落在当前水位及以下的记录（重复或乱序迟到）一律丢弃，
    水位只增不减。stats() 里的 dropped 是累计丢弃条数。

    initial_watermark: 重启恢复时传入已确认水位，先认水位再接数。
    """

    def __init__(self, initial_watermark=0):
        if initial_watermark < 0:
            raise ValueError("initial_watermark must be >= 0")
        self._received = []
        self._watermark = initial_watermark
        self._batches = 0
        self._dropped = 0

    def push(self, records):
        """接收一批记录，丢弃 seq <= watermark 的，返回接收后的水位。"""
        self._batches += 1
        for record in records:
            if record.seq <= self._watermark:
                self._dropped += 1
                continue
            self._received.append(record)
            if record.seq > self._watermark:
                self._watermark = record.seq
        return self._watermark

    def adopt_watermark(self, seq):
        """把外部确认的水位接进来，只准往前。"""
        if seq < self._watermark:
            raise ValueError("watermark can only advance")
        self._watermark = seq

    @property
    def watermark(self):
        return self._watermark

    def received(self):
        """按到达顺序返回真正收下的记录快照，新列表，调用方随便改。"""
        return list(self._received)

    def stats(self):
        """计数快照，返回独立 dict。"""
        return {
            "batches": self._batches,
            "received": len(self._received),
            "watermark": self._watermark,
            "dropped": self._dropped,
        }


_WM_MAGIC = "RXC1"
_WM_SEP = "\t"


class WatermarkStore:
    """确认水位的追加式落盘存储。

    每条记录一行：RXC1<TAB>seq<TAB>pushed<TAB>ts<TAB>crc，crc 覆盖
    行内前面全部字节。save 一次性追加整行并 flush+fsync：要么整条
    在，要么不在。读盘时第一处缺字段、校验不过、序号不递增的行起，
    包括半截尾行，全部判废并截掉，只认连续完好的前缀；水位因此不
    会跑到实际已推的前头。历史水位全部保留（points()）。
    """

    def __init__(self, path, fsync=True):
        self._path = path
        self._fsync = fsync
        self._points = []  # [(seq, pushed, ts), ...]

    def load(self):
        """读盘校验，返回最新确认水位；无文件时为 0。"""
        self._points = []
        try:
            with open(self._path, "r", encoding="utf-8", newline="") as fh:
                content = fh.read()
        except FileNotFoundError:
            return 0
        valid_bytes = 0
        prev_seq = 0
        for raw_line in content.splitlines(keepends=True):
            point = _parse_watermark_line(raw_line)
            if point is None or point[0] <= prev_seq:
                break
            self._points.append(point)
            valid_bytes += len(raw_line.encode("utf-8"))
            prev_seq = point[0]
        if valid_bytes < len(content.encode("utf-8")):
            self._truncate(valid_bytes)
        return self._points[-1][0] if self._points else 0

    def save(self, seq, pushed=0, ts=0.0):
        """确认下游收妥后追加一个水位点，seq 必须大于上一水位。"""
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
            raise ValueError("seq must be a non-negative int")
        if seq <= self.watermark:
            raise ValueError("watermark can only advance")
        body = _WM_SEP.join(
            [_WM_MAGIC, str(seq), str(int(pushed)), repr(float(ts))]
        )
        crc = "%08x" % (zlib.crc32(body.encode("utf-8")) & 0xFFFFFFFF)
        line = body + _WM_SEP + crc + "\n"
        with open(self._path, "a", encoding="utf-8", newline="") as fh:
            fh.write(line)
            fh.flush()
            if self._fsync:
                os.fsync(fh.fileno())
        self._points.append((seq, int(pushed), float(ts)))
        return seq

    def points(self):
        """返回全部完好水位点 [(seq, pushed, ts), ...] 的快照。"""
        return list(self._points)

    @property
    def watermark(self):
        """最新确认水位，没读过盘也不报错（视为 0）。"""
        return self._points[-1][0] if self._points else 0

    @property
    def pushed(self):
        """最新水位点记录的累计推送条数。"""
        return self._points[-1][1] if self._points else 0

    def _truncate(self, size):
        with open(self._path, "r+b") as fh:
            fh.truncate(size)
            fh.flush()
            if self._fsync:
                os.fsync(fh.fileno())


def _parse_watermark_line(raw_line):
    """解析单行水位记录，任何不完好都返回 None。"""
    if not raw_line.endswith("\n"):
        return None  # 没写全的尾行：哪怕正文齐了也按半截判废
    line = raw_line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    parts = line.split(_WM_SEP)
    if len(parts) != 5 or parts[0] != _WM_MAGIC:
        return None
    crc_text = parts[4]
    body = _WM_SEP.join(parts[:4])
    if len(crc_text) != 8:
        return None
    try:
        crc = int(crc_text, 16)
    except ValueError:
        return None
    if crc != (zlib.crc32(body.encode("utf-8")) & 0xFFFFFFFF):
        return None
    try:
        seq = int(parts[1])
        pushed = int(parts[2])
        ts = float(parts[3])
    except ValueError:
        return None
    if seq < 1 or pushed < 0:
        return None
    return (seq, pushed, ts)


class BoundedBuffer:
    """有界缓冲，满了 put 就阻塞：背压传回来源侧。

    blocked 记录生产侧被阻塞的次数；on_block 回调在真正挂起前
    触发，便于观测。put(None) 表示没有更多数据。
    """

    def __init__(self, capacity, on_block=None):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._items = []
        self._lock = threading.Lock()
        self._not_full = threading.Condition(self._lock)
        self._not_empty = threading.Condition(self._lock)
        self._shutdown = False
        self._blocked = 0
        self._on_block = on_block

    def put(self, item):
        with self._lock:
            if len(self._items) >= self._capacity:
                self._blocked += 1
                if self._on_block is not None:
                    self._on_block()
                while len(self._items) >= self._capacity and not self._shutdown:
                    self._not_full.wait()
                if self._shutdown:
                    return
            self._items.append(item)
            self._not_empty.notify()

    def get(self):
        with self._lock:
            while not self._items and not self._shutdown:
                self._not_empty.wait()
            if not self._items:
                return None
            item = self._items.pop(0)
            self._not_full.notify_all()
            return item

    @property
    def closed(self):
        with self._lock:
            return self._shutdown

    def shutdown(self):
        """放开所有等待方，停止接收新记录。"""
        with self._lock:
            self._shutdown = True
            self._not_empty.notify_all()
            self._not_full.notify_all()

    @property
    def blocked(self):
        with self._lock:
            return self._blocked


class StreamRunner:
    """把来源记录按批推给下游。

    source: 提供 fetch(after_seq, limit) 的来源。
    sink: 提供 push(records) 的下游。
    batch_size: 每批最多推送的记录条数。
    clock: 注入时钟，用于给进度打时间戳。
    store: 可选 WatermarkStore。给了就先认盘上水位再续推，每批
        下游收妥后追加确认水位。
    buffer_size: 可选有界缓冲容量。给了就用独立线程从来源取数，
        缓冲满即背压阻塞，不再从来源取。
    on_block: 缓冲挂起前的回调，便于观测阻塞。
    pre_push: 每批推送前的回调，便于在测试里卡住下游。
    """

    def __init__(
        self,
        source,
        sink,
        batch_size=2,
        clock=time.monotonic,
        store=None,
        buffer_size=None,
        on_block=None,
        pre_push=None,
    ):
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if buffer_size is not None and buffer_size < 1:
            raise ValueError("buffer_size must be >= 1")
        self._source = source
        self._sink = sink
        self._batch_size = batch_size
        self._clock = clock
        self._store = store
        self._buffer_size = buffer_size
        self._on_block = on_block
        self._pre_push = pre_push
        self._last_seq = 0
        self._pushed = 0
        self._batches = 0
        self._last_at = None
        self._dropped = 0
        self._blocked = 0
        self._buffer = None
        if store is not None:
            self._restore(store.load())

    def _restore(self, seq):
        """启动先认水位：游标、计数和下游水位都对齐到确认点。"""
        self._last_seq = seq
        self._pushed = self._store.pushed
        adopt = getattr(self._sink, "adopt_watermark", None)
        if adopt is not None:
            adopt(seq)

    def run(self):
        """逐批取数并推送，直到来源没有新记录，返回本次推送的记录条数。"""
        if self._buffer_size is not None:
            return self._run_buffered()
        moved = 0
        cursor = self._last_seq
        while True:
            batch = self._source.fetch(cursor, self._batch_size)
            if not batch:
                break
            ts = self._clock()
            moved += self._deliver(batch, ts)
            cursor = max(batch[-1].seq, self._last_seq)
            self._batches += 1
            self._last_at = ts
        return moved

    def _run_buffered(self):
        """取数线程受有界缓冲背压，推送线程按批确认水位。"""
        buffer = BoundedBuffer(self._buffer_size, on_block=self._on_block)
        self._buffer = buffer
        state = {"cursor": self._last_seq}
        producer_error = []

        def produce():
            try:
                while not buffer.closed:
                    batch = self._source.fetch(state["cursor"], self._batch_size)
                    if not batch:
                        break
                    for record in batch:
                        buffer.put(record)
                    # 批次被整窗丢弃时只越过批次末端，正常时对齐确认水位
                    state["cursor"] = max(batch[-1].seq, self._last_seq)
            except BaseException as exc:  # 传回主线程重抛
                producer_error.append(exc)
            finally:
                buffer.put(None)

        worker = threading.Thread(target=produce, daemon=True)
        worker.start()

        moved = 0
        pending = []
        try:
            while not buffer.closed:
                record = buffer.get()
                if record is None:
                    break
                pending.append(record)
                if len(pending) == self._batch_size:
                    if self._pre_push is not None:
                        self._pre_push(pending)
                    ts = self._clock()
                    moved += self._deliver(pending, ts)
                    self._batches += 1
                    self._last_at = ts
                    pending = []
            if pending:
                if self._pre_push is not None:
                    self._pre_push(pending)
                ts = self._clock()
                moved += self._deliver(pending, ts)
                self._batches += 1
                self._last_at = ts
        finally:
            worker.join(timeout=1.0)
            buffer.shutdown()
            self._blocked = buffer.blocked
        if producer_error:
            raise producer_error[0]
        return moved

    def _deliver(self, batch, ts):
        """推送一批，下游收妥后才推进并落盘确认水位，返回新收下条数。"""
        stats_fn = getattr(self._sink, "stats", None)
        before_dropped = stats_fn().get("dropped", 0) if callable(stats_fn) else 0
        self._sink.push(batch)
        dropped = (
            stats_fn().get("dropped", before_dropped) - before_dropped
            if callable(stats_fn)
            else 0
        )
        after = self._sink.watermark
        if dropped < 0:
            dropped = 0
        accepted = len(batch) - dropped
        self._dropped += dropped
        self._pushed += accepted
        if after > self._last_seq:
            self._last_seq = after
            if self._store is not None:
                self._store.save(after, self._pushed, ts)
        return accepted

    def progress(self):
        """进度快照，返回独立 dict，调用方随便改。"""
        dropped = self._dropped
        blocked = self._blocked
        if self._buffer is not None:
            blocked = self._buffer.blocked
        stats_fn = getattr(self._sink, "stats", None)
        if callable(stats_fn):
            dropped = stats_fn().get("dropped", dropped)
        return {
            "last_seq": self._last_seq,
            "pushed": self._pushed,
            "batches": self._batches,
            "last_at": self._last_at,
            "dropped": dropped,
            "blocked": blocked,
        }
