"""把上游的记录按批推给下游。

来源与下游都是注入的内存对象，用来顶替真实 IO。搬运器逐批取数、
推送，并把进度记在内存里：推了多少条、走到哪个序号、推了几批。

断流续传三件套：
- WatermarkSink 认水位，序号不高于水位的重复与乱序记录一律丢弃并计数；
- StreamRunner 传入 store（如 resumex.checkpoint.WatermarkLog）后，
  启动先认落盘水位、按水位之后取数，下游确认收妥后才把水位落盘；
- buffer_size > 0 时推送走有界缓冲，缓冲满就停止取数并阻塞等待，
  阻塞次数与累计等待时长计入进度，形成背压。
"""

import queue
import threading
import time


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


class WatermarkSink(MemorySink):
    """认水位的下游：序号不高于水位的记录一律丢弃，水位只增不减。

    重复到达（同一序号收到两次）和乱序到达（序号比水位还低）都算丢，
    计入 dropped；只有序号严格大于当前水位的记录才留档并推进水位。
    """

    def __init__(self, watermark=0):
        super().__init__()
        self._watermark = watermark
        self._dropped = 0

    def align(self, watermark):
        """启动时认水位：只接受更高的水位，绝不往后退。"""
        if watermark > self._watermark:
            self._watermark = watermark
        return self._watermark

    def push(self, records):
        """接收一批记录，丢弃 seq <= watermark 的，返回接收后的水位。"""
        self._batches += 1
        for record in records:
            if record.seq <= self._watermark:
                self._dropped += 1
                continue
            self._received.append(record)
            self._watermark = record.seq
        return self._watermark

    @property
    def dropped(self):
        return self._dropped

    def stats(self):
        """计数快照，在基线三键之外多给 dropped。"""
        stats = super().stats()
        stats["dropped"] = self._dropped
        return stats


class StreamRunner:
    """把来源记录按批推给下游。

    source: 提供 fetch(after_seq, limit) 的来源。
    sink: 提供 push(records) 的下游。
    batch_size: 每批最多推送的记录条数。
    clock: 注入时钟，用于给进度打时间戳。
    store: 可选的水位落盘对象，提供 load()/commit(seq, stamped_at=)；
      给了就支持断点续传：启动先认水位，按水位之后取数，下游确认
      收妥后再把水位落盘。不给则保持纯内存的基线行为。
    buffer_size: 待推送批的有界缓冲容量（单位：批）。0 表示直推；
      > 0 时取数与推送解耦，缓冲到上限就不再从来源取数，阻塞等待
      并把阻塞次数与等待时长计入进度，构成对来源的背压。
    """

    def __init__(
        self,
        source,
        sink,
        batch_size=2,
        clock=time.monotonic,
        store=None,
        buffer_size=0,
    ):
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if buffer_size < 0:
            raise ValueError("buffer_size must be >= 0")
        self._source = source
        self._sink = sink
        self._batch_size = batch_size
        self._clock = clock
        self._store = store
        self._buffer_size = buffer_size
        self._last_seq = self._starting_watermark()
        self._pushed = 0
        self._batches = 0
        self._last_at = None
        self._blocked = 0
        self._blocked_for = 0.0

    def _starting_watermark(self):
        """启动先认水位：取落盘水位，并让下游对齐到同一处。"""
        if self._store is None:
            return 0
        watermark = self._store.load()
        align = getattr(self._sink, "align", None)
        if align is not None:
            watermark = align(watermark)
        return watermark

    def run(self):
        """逐批取数并推送，直到来源没有新记录，返回本次推送的记录条数。"""
        if self._buffer_size:
            return self._run_buffered()
        moved = 0
        while True:
            batch = self._source.fetch(self._last_seq, self._batch_size)
            if not batch:
                break
            confirmed = self._sink.push(batch)
            if self._store is None:
                self._last_seq = batch[-1].seq
            else:
                # 先确认下游收妥，再落水位；sink 丢弃时返回当前水位，
                # 存储侧也保证水位只增不减。
                self._last_seq = confirmed
                self._store.commit(confirmed, stamped_at=self._clock())
            moved += len(batch)
            self._pushed += len(batch)
            self._batches += 1
            self._last_at = self._clock()
        return moved

    def _run_buffered(self):
        """有界缓冲：生产者取数，缓冲满就停取阻塞；消费者推送并落盘。"""
        pending = queue.Queue(self._buffer_size)
        slot = threading.BoundedSemaphore(self._buffer_size)
        lock = threading.Lock()
        failure = []

        def consume():
            while True:
                batch = pending.get()
                if batch is None:
                    pending.task_done()
                    return
                try:
                    confirmed = self._sink.push(batch)
                    stamped_at = self._clock()
                    if self._store is not None:
                        confirmed = self._store.commit(
                            confirmed, stamped_at=stamped_at
                        )
                    with lock:
                        self._pushed += len(batch)
                        self._batches += 1
                        self._last_at = stamped_at
                        if confirmed > self._last_seq:
                            self._last_seq = confirmed
                except Exception as exc:  # 记下交给 run() 重新抛出
                    failure.append(exc)
                    slot.release()
                    pending.task_done()
                    return
                slot.release()
                pending.task_done()

        worker = threading.Thread(target=consume, name="resumex-pump")
        worker.start()
        moved = 0
        cursor = self._last_seq  # 取数游标只随已取走的批推进
        try:
            while not failure:
                if not slot.acquire(blocking=False):
                    # 缓冲到上限，不再从来源取数，阻塞等空位。
                    self._blocked += 1
                    wait_started = self._clock()
                    while not slot.acquire(timeout=0.05):
                        if failure:
                            break
                    self._blocked_for += self._clock() - wait_started
                if failure:
                    break
                batch = self._source.fetch(cursor, self._batch_size)
                if not batch:
                    slot.release()
                    break
                cursor = batch[-1].seq
                moved += len(batch)
                pending.put(batch)
        finally:
            pending.put(None)
            worker.join()
        if failure:
            raise failure[0]
        return moved

    def progress(self):
        """进度快照，返回独立 dict，调用方随便改。"""
        return {
            "last_seq": self._last_seq,
            "pushed": self._pushed,
            "batches": self._batches,
            "last_at": self._last_at,
            "blocked": self._blocked,
            "blocked_for": self._blocked_for,
        }
