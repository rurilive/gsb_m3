"""把上游的记录按批推给下游。

来源与下游都是注入的内存对象，用来顶替真实 IO。搬运器逐批取数、
推送，并把进度记在内存里：推了多少条、走到哪个序号、推了几批。

重启续传：WatermarkStore 把下游确认过的水位以多条带校验的记录
追加落盘，启动时只认完好记录里的最后一个水位，半截记录一律作废，
所以水位只会停在实际已推且已落盘的位置，不会跑到前头。

重复与乱序：序号不大于当前水位的记录一律丢弃并计数，水位只增不减。

背压：缓冲有界，缓冲满时来源取数被阻塞，阻塞次数计入进度。
"""

import os
import queue
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
    seq 不大于水位的记录（重复或乱序迟到）一律丢弃，计入 discarded。
    """

    def __init__(self):
        self._received = []
        self._watermark = 0
        self._batches = 0
        self._discarded = 0
        self._lock = threading.RLock()

    def push(self, records):
        """接收一批记录，返回接收后的水位。

        seq <= 当前水位的记录按丢处理；水位只随更大的序号前移。
        """
        with self._lock:
            self._batches += 1
            for record in records:
                if record.seq <= self._watermark:
                    self._discarded += 1
                    continue
                self._received.append(record)
                self._watermark = record.seq
            return self._watermark

    @property
    def watermark(self):
        with self._lock:
            return self._watermark

    @property
    def discarded(self):
        """重复或乱序迟到而被丢弃的记录条数。"""
        with self._lock:
            return self._discarded

    def received_count(self):
        """实际收下（未被丢弃）的记录条数。"""
        with self._lock:
            return len(self._received)

    def received(self):
        """按到达顺序返回已收到记录的快照，新列表，调用方随便改。"""
        with self._lock:
            return list(self._received)

    def stats(self):
        """计数快照，返回独立 dict。"""
        with self._lock:
            return {
                "batches": self._batches,
                "received": len(self._received),
                "watermark": self._watermark,
                "discarded": self._discarded,
            }


class WatermarkStore:
    """水位落盘：追加写、带 CRC32 校验，保留多个历史水位点。

    每行一条完整记录，制表符分隔、行尾换行：
    ``RX1 <seq> <at> <payload 字节数> <payload 的 hex> <crc32>``。
    crc32 覆盖除末列外的整行。读盘时逐行校验，魔数、列数、校验和、
    序号单调任一不满足都视为废行（半截写入或损坏），只有完好行
    算数，所以崩溃留下的半截记录绝不会把水位推到实际已推的前头。
    """

    _MAGIC = "RX1"

    def __init__(self, path):
        self._path = path
        self._lock = threading.RLock()
        self._points = []  # [(seq, at, payload), ...]，均为校验通过的完好点
        self._load()

    def _load(self):
        if not os.path.exists(self._path):
            return
        with open(self._path, "rb") as fh:
            data = fh.read()
        last_seq = 0
        for raw in data.split(b"\n"):
            if not raw:
                continue
            parsed = self._parse_line(raw)
            if parsed is None:
                continue
            seq, at, payload = parsed
            if seq <= last_seq:
                # 水位只准往前：回退或重复的落盘点同样拒绝。
                continue
            self._points.append((seq, at, payload))
            last_seq = seq

    @classmethod
    def _parse_line(cls, raw):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
        parts = text.split("\t")
        if len(parts) != 6 or parts[0] != cls._MAGIC:
            return None
        try:
            seq = int(parts[1])
            at = float(parts[2])
            size = int(parts[3])
            payload = bytes.fromhex(parts[4])
            expected = int(parts[5], 16)
        except ValueError:
            return None
        if seq < 1 or size != len(payload):
            return None
        body = "\t".join(parts[:5]).encode("utf-8")
        if (zlib.crc32(body) & 0xFFFFFFFF) != expected:
            return None
        return seq, at, payload

    @classmethod
    def _encode_line(cls, seq, at, payload):
        body = "%s\t%d\t%.17g\t%d\t%s" % (
            cls._MAGIC,
            seq,
            at,
            len(payload),
            payload.hex(),
        )
        checksum = zlib.crc32(body.encode("utf-8")) & 0xFFFFFFFF
        return ("%s\t%08x\n" % (body, checksum)).encode("utf-8")

    def save(self, seq, at, payload=b""):
        """下游确认收妥后调用，追加落盘一个水位点。

        整行编码后一次 write，再 flush + fsync；序号必须大于当前
        已落盘水位（水位只增不减），否则拒绝。
        """
        if not isinstance(payload, (bytes, bytearray)):
            raise ValueError("payload must be bytes")
        with self._lock:
            if seq <= self.latest_seq:
                raise ValueError("watermark seq must be strictly increasing")
            line = self._encode_line(seq, at, bytes(payload))
            with open(self._path, "ab") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
            self._points.append((seq, at, bytes(payload)))

    @property
    def latest_seq(self):
        """最后一个完好水位点的序号，无有效记录时为 0。"""
        with self._lock:
            return self._points[-1][0] if self._points else 0

    def history(self):
        """返回全部完好水位点的快照列表（旧到新）。"""
        with self._lock:
            return list(self._points)


class StreamRunner:
    """把来源记录按批推给下游。

    source: 提供 fetch(after_seq, limit) 的来源。
    sink: 提供 push(records) 的下游。
    batch_size: 每批最多推送的记录条数。
    clock: 注入时钟，用于给进度打时间戳。
    store: 可选的 WatermarkStore。传入时启动先认盘上水位，从水位
           之后取数；每批下游确认收妥后再落盘新水位。
    max_buffered: 内存缓冲上限（按记录条数计）。None 时取数与推送
           同步直推；给正数时走有界缓冲，缓冲满即对来源取数形成
           背压（阻塞计入 blocked）。
    """

    def __init__(
        self,
        source,
        sink,
        batch_size=2,
        clock=time.monotonic,
        store=None,
        max_buffered=None,
    ):
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if max_buffered is not None and max_buffered < 1:
            raise ValueError("max_buffered must be >= 1 or None")
        self._source = source
        self._sink = sink
        self._batch_size = batch_size
        self._clock = clock
        self._store = store
        self._max_buffered = max_buffered
        self._cursor = store.latest_seq if store is not None else 0
        self._last_seq = self._cursor
        self._pushed = 0
        self._batches = 0
        self._blocked = 0
        self._last_at = None
        self._worker_error = None

    def run(self):
        """逐批取数并推送，直到来源没有新记录，返回本次下游收下的条数。

        启动先认 store 里的水位（若有），只从水位之后取数，已确认
        过的不会重喂。
        """
        if self._max_buffered is None:
            return self._run_inline()
        return self._run_buffered()

    def _run_inline(self):
        moved = 0
        while True:
            batch = self._source.fetch(self._cursor, self._batch_size)
            if not batch:
                break
            moved += self._deliver(batch)
            self._cursor = max(self._cursor, batch[-1].seq)
        return moved

    def _run_buffered(self):
        slots = max(1, self._max_buffered // self._batch_size)
        bounded = queue.Queue(maxsize=slots)
        self._worker_error = None
        pushed_at_start = self._pushed

        def worker():
            try:
                while True:
                    batch = bounded.get()
                    try:
                        if batch is None:
                            return
                        self._deliver(batch)
                    finally:
                        bounded.task_done()
            except BaseException as exc:  # 交回生产者线程重抛
                self._worker_error = exc

        thread = threading.Thread(target=worker, name="resumex-sink")
        thread.daemon = True
        thread.start()

        try:
            while True:
                if self._worker_error is not None:
                    raise self._worker_error
                batch = self._source.fetch(self._cursor, self._batch_size)
                if not batch:
                    while self._worker_error is None:
                        with bounded.all_tasks_done:
                            if bounded.unfinished_tasks == 0:
                                break
                        time.sleep(0.005)
                    if self._worker_error is not None:
                        raise self._worker_error
                    break
                if bounded.full():
                    self._blocked += 1  # 背压：缓冲满，停止从来源取
                # 满时在此等待，直到下游腾出位置；worker 崩了也要醒。
                while True:
                    try:
                        bounded.put(batch, timeout=0.05)
                        break
                    except queue.Full:
                        if self._worker_error is not None:
                            raise self._worker_error
                self._cursor = max(self._cursor, batch[-1].seq)
        finally:
            if self._worker_error is None:
                bounded.put(None)
                thread.join()
            else:
                thread.join(timeout=1.0)

        return self._pushed - pushed_at_start

    def _deliver(self, batch):
        """一批交下游，确认收妥后再推进水位并落盘，返回新收下条数。"""
        before = self._sink_received_count()
        self._sink.push(batch)
        accepted = self._sink_received_count() - before
        self._last_seq = max(self._last_seq, self._sink_watermark())
        self._pushed += accepted
        self._batches += 1
        self._last_at = self._clock()
        if self._store is not None:
            watermark = self._sink_watermark()
            if watermark > self._store.latest_seq:
                self._store.save(watermark, self._last_at)
        return accepted

    def _sink_received_count(self):
        if hasattr(self._sink, "received_count"):
            return self._sink.received_count()
        return len(self._sink.received())

    def _sink_watermark(self):
        return self._sink.watermark

    def _sink_discarded(self):
        if hasattr(self._sink, "stats"):
            return self._sink.stats().get("discarded", 0)
        return 0

    def progress(self):
        """进度快照，返回独立 dict，调用方随便改。"""
        return {
            "last_seq": self._last_seq,
            "pushed": self._pushed,
            "batches": self._batches,
            "last_at": self._last_at,
            "discarded": self._sink_discarded(),
            "blocked": self._blocked,
            "watermark": self._store.latest_seq if self._store is not None else None,
        }
