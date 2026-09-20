"""断点续传：水位落盘、去重、背压。

WatermarkStore 把下游确认过的水位追加写进日志文件，一行一条，
带 crc32 校验；只认以换行结尾且校验通过的整行，写一半的尾行
加载时直接丢弃。ResumableRunner 启动时先读水位，从水位之后取数；
序号落在水位及以下（或缓冲中已有）的记录一律丢弃并计数；缓冲
到上限就暂停从来源取数，阻塞次数也计数。水位只在下游确认收妥
后才落盘，且只增不减。
"""

import json
import os
import time
import zlib


def _crc_of(seq):
    return zlib.crc32(str(seq).encode("ascii")) & 0xFFFFFFFF


class WatermarkStore:
    """水位日志：append-only 文件，每行一条 {"seq": N, "crc": C}。

    path: 水位文件路径，不存在时视为空。
    keep: history() 最多返回的历史点个数。
    """

    def __init__(self, path, keep=5):
        if keep < 1:
            raise ValueError("keep must be >= 1")
        self._path = path
        self._keep = keep
        self._points = self._load()

    def _load(self):
        try:
            with open(self._path, "rb") as fh:
                data = fh.read()
        except FileNotFoundError:
            return []
        points = []
        # split 后最后一段：文件以换行结尾时是空串，否则是没写完的半截记录，都丢掉。
        for chunk in data.split(b"\n")[:-1]:
            seq = self._parse(chunk)
            if seq is not None:
                points.append(seq)
        return points

    @staticmethod
    def _parse(chunk):
        try:
            obj = json.loads(chunk.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        if not isinstance(obj, dict):
            return None
        seq = obj.get("seq")
        if type(seq) is not int or seq < 0:
            return None
        if obj.get("crc") != _crc_of(seq):
            return None
        return seq

    def append(self, seq):
        """落一条已确认水位，必须不小于当前水位，写完即 fsync。"""
        if type(seq) is not int or seq < 0:
            raise ValueError("seq must be a non-negative int")
        if self._points and seq < max(self._points):
            raise ValueError("watermark must not go backward")
        line = json.dumps({"seq": seq, "crc": _crc_of(seq)}).encode("ascii") + b"\n"
        with open(self._path, "ab") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        self._points.append(seq)

    def latest(self):
        """最新有效水位，没有时返回 0。"""
        return max(self._points) if self._points else 0

    def history(self):
        """最近 keep 个有效水位点，按落盘顺序，新列表。"""
        return list(self._points[-self._keep:])


class ResumableRunner:
    """带水位落盘、去重与背压的搬运器。

    source: 提供 fetch(after_seq, limit) 的来源。
    sink: 提供 push(records) 的下游，返回确认后的水位。
    store: WatermarkStore，启动时先认里面的水位。
    batch_size: 每批最多从来源取的条数。
    buffer_size: 未确认缓冲上限，满了就暂停从来源取数（背压）。
    clock: 注入时钟。
    """

    def __init__(self, source, sink, store, batch_size=2, buffer_size=None,
                 clock=time.monotonic):
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if buffer_size is None:
            buffer_size = batch_size
        if buffer_size < 1:
            raise ValueError("buffer_size must be >= 1")
        self._source = source
        self._sink = sink
        self._store = store
        self._batch_size = batch_size
        self._buffer_size = buffer_size
        self._clock = clock
        self._watermark = store.latest()
        self._fetch_seq = self._watermark
        self._pushed = 0
        self._dropped = 0
        self._blocked = 0
        self._batches = 0
        self._last_at = None

    @property
    def watermark(self):
        return self._watermark

    def run(self):
        """逐批取数推送直到来源没有新记录，返回本次推送条数。"""
        moved = 0
        buffer = []
        buffered = set()
        while True:
            while len(buffer) < self._buffer_size:
                room = self._buffer_size - len(buffer)
                batch = self._source.fetch(self._fetch_seq,
                                           min(self._batch_size, room))
                if not batch:
                    break
                for record in batch:
                    if record.seq > self._fetch_seq:
                        self._fetch_seq = record.seq
                    if record.seq <= self._watermark or record.seq in buffered:
                        self._dropped += 1
                    else:
                        buffer.append(record)
                        buffered.add(record.seq)
            if not buffer:
                break
            if len(buffer) >= self._buffer_size:
                self._blocked += 1
            confirmed = self._sink.push(list(buffer))
            new_watermark = max([self._watermark, confirmed]
                                + [r.seq for r in buffer])
            if new_watermark > self._watermark:
                self._store.append(new_watermark)
                self._watermark = new_watermark
            moved += len(buffer)
            self._pushed += len(buffer)
            self._batches += 1
            self._last_at = self._clock()
            buffer = []
            buffered = set()
        return moved

    def stats(self):
        """计数快照：水位、推送、丢弃、阻塞、批数，返回独立 dict。"""
        return {
            "watermark": self._watermark,
            "pushed": self._pushed,
            "dropped": self._dropped,
            "blocked": self._blocked,
            "batches": self._batches,
            "last_at": self._last_at,
        }
