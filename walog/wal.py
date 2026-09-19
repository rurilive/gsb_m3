"""预写日志主体：帧格式 [2B 长度(小端)][JSON 载荷][4B CRC(大端)]，超过段大小切段。"""

import json
import os
import re
import struct
import threading
import zlib
from pathlib import Path

_LEN_HEAD = 2
_CRC_TAIL = 4
_SEG_RE = re.compile(r"^wal-(\d+)\.log$")


def _unpack_length(head: bytes) -> int:
    return struct.unpack("<H", head)[0]


class WriteAheadLog:
    """多段追加日志。record 为 dict，写入时自动带上单调递增的 seq。"""

    def __init__(self, directory, max_segment_bytes: int = 1 << 20):
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_segment = max_segment_bytes
        self._lock = threading.RLock()
        self._seq = 0
        self._seg_no = self._latest_segment_no()
        self._fh = None
        self._size = 0
        self._roll()

    # ---- 内部：路径与切段 -----------------------------------------------------
    def _segment_path(self, no: int) -> Path:
        return self._dir / f"wal-{no}.log"

    def _segments(self) -> list:
        found = []
        for path in self._dir.glob("wal-*.log"):
            m = _SEG_RE.match(path.name)
            if m:
                found.append((int(m.group(1)), path))
        return [path for _, path in sorted(found)]

    def _latest_segment_no(self) -> int:
        nos = []
        for path in self._dir.glob("wal-*.log"):
            m = _SEG_RE.match(path.name)
            if m:
                nos.append(int(m.group(1)))
        return max(nos, default=0)

    def _sync_dir(self) -> None:
        """fsync 目录，保证新建段文件的目录项落盘。"""
        fd = os.open(self._dir, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _roll(self) -> None:
        if self._fh is not None:
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._fh.close()
        self._seg_no += 1
        self._fh = open(self._segment_path(self._seg_no), "ab")
        self._size = 0
        self._sync_dir()

    # ---- 对外 API -------------------------------------------------------------
    def append(self, record: dict) -> int:
        """追加一条记录，返回分配的 seq。"""
        with self._lock:
            self._seq += 1
            rec = dict(record)
            rec["seq"] = self._seq
            payload = json.dumps(
                rec, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(payload) > 0xFFFF:
                raise ValueError(f"record payload too large: {len(payload)} bytes")
            head = struct.pack("<H", len(payload))
            frame = head + payload + struct.pack(">I", zlib.crc32(head + payload))
            self._fh.write(frame)
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._size += len(frame)
            if self._size >= self._max_segment:
                self._roll()
            return self._seq

    def replay(self) -> list:
        """读出全部记录（恢复入口），seq 水位推进到已见的最大值。"""
        records = []
        with self._lock:
            for path in self._segments():
                for rec in self._read_frames(path):
                    records.append(rec)
            if records:
                self._seq = max(self._seq, max(r["seq"] for r in records))
        return records

    def checkpoint(self) -> None:
        """把当前日志落盘并切新段。"""
        with self._lock:
            self._roll()

    def close(self) -> None:
        with self._lock:
            if self._fh is not None:
                self._fh.flush()
                os.fsync(self._fh.fileno())
                self._fh.close()
                self._fh = None

    # ---- 内部：帧解码 ---------------------------------------------------------
    def _read_frames(self, path: Path):
        """逐帧解码，遇到坏帧（CRC 不符或截断）即停，丢弃断电留下的半帧。"""
        with open(path, "rb") as f:
            while True:
                head = f.read(_LEN_HEAD)
                if len(head) < _LEN_HEAD:
                    return
                length = _unpack_length(head)
                payload = f.read(length)
                if len(payload) < length:
                    return
                crc_raw = f.read(_CRC_TAIL)
                if len(crc_raw) < _CRC_TAIL:
                    return
                crc_val = struct.unpack(">I", crc_raw)[0]
                if zlib.crc32(head + payload) != crc_val:
                    return
                try:
                    yield json.loads(payload)
                except ValueError:
                    return
