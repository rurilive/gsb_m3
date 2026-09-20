"""已确认水位的落盘日志。

日志是只追加的行式文件，每个完好点占一行，保留最近若干个水位点：

    resumex-v1\t<seq>\t<clock>\t<sha1(seq + clock)>\n

读取时只认五段齐全、版本与校验和都对得上的行；写崩留下的半截行、
被改坏的行一律作废，绝不当成有效水位。压缩时先写临时文件再
os.replace 原子换名，换名之后的文件要么是旧的、要么是完整的新文件。
"""

import hashlib
import os
import time

_VERSION = "resumex-v1"


class WatermarkLog:
    """把已确认的水位点追加到文件，重启后读出最大的完好水位。"""

    def __init__(self, path, keep=8, clock=time.monotonic):
        if keep < 1:
            raise ValueError("keep must be >= 1")
        self._path = path
        self._keep = keep
        self._clock = clock
        self._entries = self._read_all()

    @property
    def watermark(self):
        """日志里最新一个完好水位，空日志为 0。"""
        return self._entries[-1][0] if self._entries else 0

    def load(self):
        """启动先认水位：返回日志里最新的完好水位。"""
        return self.watermark

    def points(self):
        """保留下来的完好水位点快照 [(seq, clock), ...]，按序号递增。"""
        return list(self._entries)

    def commit(self, seq, stamped_at=None):
        """确认下游收妥后追加一个水位点，返回当前有效水位。

        水位只准往前：seq 不大于已有水位时原样返回，不落盘。
        """
        if seq is None or seq <= self.watermark:
            return self.watermark
        if stamped_at is None:
            stamped_at = self._clock()
        line = self._encode(seq, stamped_at)
        with open(self._path, "ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        self._entries.append((seq, stamped_at))
        if len(self._entries) > self._keep:
            self._compact()
        return self.watermark

    def _compact(self):
        """只留最近 keep 个点，临时文件写完原子换名。"""
        self._entries = self._entries[-self._keep:]
        directory = os.path.dirname(os.path.abspath(self._path))
        tmp_path = self._path + ".tmp"
        with open(tmp_path, "wb") as handle:
            for seq, stamped_at in self._entries:
                handle.write(self._encode(seq, stamped_at))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, self._path)
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass

    def _read_all(self):
        if not os.path.exists(self._path):
            return []
        out = []
        with open(self._path, "rb") as handle:
            raw = handle.read()
        for line in raw.splitlines():
            try:
                text = line.decode("ascii")
            except UnicodeDecodeError:
                continue
            parts = text.split("\t")
            if len(parts) != 4 or parts[0] != _VERSION:
                continue
            _, seq_text, clock_text, digest = parts
            if self._digest(seq_text, clock_text) != digest:
                continue
            try:
                seq = int(seq_text)
                clock_value = float(clock_text)
            except ValueError:
                continue
            out.append((seq, clock_value))
        return out

    @staticmethod
    def _digest(seq_text, clock_text):
        return hashlib.sha1(
            ("%s\x00%s" % (seq_text, clock_text)).encode("ascii")
        ).hexdigest()

    def _encode(self, seq, stamped_at):
        seq_text = str(int(seq))
        clock_text = repr(float(stamped_at))
        digest = self._digest(seq_text, clock_text)
        return ("%s\t%s\t%s\t%s\n" % (
            _VERSION, seq_text, clock_text, digest,
        )).encode("ascii")
