"""预写日志主体：帧格式 [2B 长度][JSON 载荷][4B CRC]，超过段大小切段。"""

import json
import os
import struct
import threading
import zlib
from pathlib import Path

_LEN_HEAD = 2
_CRC_TAIL = 4
_MAX_PAYLOAD = 0xFFFF


def _unpack_length(head: bytes) -> int:
    return int.from_bytes(head, "little")


class WriteAheadLog:
    """多段追加日志。record 为 dict，写入时自动带上单调递增的 seq。"""

    def __init__(self, directory, max_segment_bytes: int = 1 << 20):
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_segment = max_segment_bytes
        self._lock = threading.RLock()
        self._seq = 0
        self._seg_no = 0
        self._fh = None
        self._size = 0
        existing = self._segments()
        if existing:
            last = existing[-1]
            self._seg_no = self._segment_number(last)
            self._size = self._truncate_torn_tail(last)
            self._fh = open(last, "ab")
        else:
            self._roll()

    # ---- 内部：路径与切段 -----------------------------------------------------
    def _segment_path(self, no: int) -> Path:
        return self._dir / f"wal-{no}.log"

    @staticmethod
    def _segment_number(path: Path) -> int:
        return int(path.stem.split("-", 1)[1])

    def _segments(self) -> list:
        segs = []
        for path in self._dir.glob("wal-*.log"):
            try:
                segs.append((self._segment_number(path), path))
            except ValueError:
                continue
        return [path for _, path in sorted(segs)]

    def _truncate_torn_tail(self, path: Path) -> int:
        """截掉活动段尾部的撕裂帧，返回有效字节数。"""
        offset = 0
        with open(path, "rb") as f:
            while True:
                head = f.read(_LEN_HEAD)
                if len(head) < _LEN_HEAD:
                    break
                length = _unpack_length(head)
                payload = f.read(length)
                crc_raw = f.read(_CRC_TAIL)
                if len(payload) < length or len(crc_raw) < _CRC_TAIL:
                    break
                if zlib.crc32(head + payload) != int.from_bytes(crc_raw, "big"):
                    break
                offset += _LEN_HEAD + length + _CRC_TAIL
        with open(path, "r+b") as f:
            f.truncate(offset)
        return offset

    def _roll(self) -> None:
        if self._fh is not None:
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._fh.close()
        self._seg_no += 1
        self._fh = open(self._segment_path(self._seg_no), "ab")
        self._size = 0

    # ---- 对外 API -------------------------------------------------------------
    def append(self, record: dict) -> int:
        """追加一条记录，返回分配的 seq。"""
        with self._lock:
            self._seq += 1
            rec = dict(record)
            rec["seq"] = self._seq
            payload = json.dumps(
                rec, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(payload) > _MAX_PAYLOAD:
                raise ValueError(
                    f"record payload too large: {len(payload)} > {_MAX_PAYLOAD}")
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
        """逐帧解码，遇到坏帧即停。"""
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
                crc_val = int.from_bytes(crc_raw, "big")
                if zlib.crc32(head + payload) != crc_val:
                    return
                try:
                    yield json.loads(payload)
                except ValueError:
                    return
