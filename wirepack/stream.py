"""按块喂入的定长记录解码器。

来源怎么切块是来源的自由：记录可能跨块，一块里也可能挤着好几条记录。
RecordStream 只保留凑不满一条记录的尾巴，消费过的字节立刻丢掉。
"""

from wirepack.errors import DecodeError
from wirepack.errors import FrameDecodeError
from wirepack.frame import FRAME_MAGIC, MAX_FRAME_SIZE, _MAGIC_BYTE, _NeedMore, _frame_at
from wirepack.records import RECORD_SIZE, unpack_record


def chunked(data, size):
    """把一段字节按固定大小切片，最后一块可以不满。"""
    if size <= 0:
        raise ValueError("size 必须为正数: %r" % (size,))
    return [data[i:i + size] for i in range(0, len(data), size)]


class RecordStream:
    """定长记录的流式解码器。

    feed() 吃任意大小的字节块，吐出这次凑齐的记录；
    offset 是已经消费掉的字节数，pending 是还留在缓冲里的字节数。
    """

    def __init__(self):
        self._buf = bytearray()
        self.offset = 0
        self.records = 0

    @property
    def pending(self):
        return len(self._buf)

    def feed(self, chunk):
        """喂一块字节，返回本次解出的记录列表。"""
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise TypeError("chunk 需要字节串，收到 %r" % (type(chunk).__name__,))
        self._buf += chunk
        out = []
        while len(self._buf) >= RECORD_SIZE:
            try:
                record, _ = unpack_record(self._buf, 0)
            except DecodeError as exc:
                if exc.offset is not None:
                    exc.offset += self.offset
                raise
            del self._buf[:RECORD_SIZE]
            self.offset += RECORD_SIZE
            self.records += 1
            out.append(record)
        return out

    def finish(self):
        """流已经到末尾：缓冲里还剩半个记录就说明尾巴被截断了。"""
        if self._buf:
            raise DecodeError("流末残留 %d 字节，记录被截断" % (len(self._buf),),
                              offset=self.offset, field="record")
        return []

    def __repr__(self):
        return "RecordStream(offset=%d, records=%d, pending=%d)" % (
            self.offset, self.records, len(self._buf))


def iter_records(chunks):
    """把一串字节块解成记录序列，流末校验尾巴。"""
    stream = RecordStream()
    for chunk in chunks:
        for record in stream.feed(chunk):
            yield record
    for record in stream.finish():
        yield record


class FrameDecoder:
    """新老格式混流的按块解码器。

    首字节是 0x81 按新帧解，否则按 16 字节定长记录解（老记录首字节是
    seq 高字节，上游保证 seq < 800 万即不超过 0x7A，两种格式不会撞车）。

    feed() 吃任意切分的字节块，返回本次解出的 Record/Frame 混合列表，
    与一次性喂入的结果完全一致。新帧解失败不抛异常：错误记进 errors
    （FrameDecodeError，带 frame_index/field/resync_at），解码器跳到
    下一个 0x81 帧头继续解。老记录解失败同样记进 errors（frame_index
    为 None）并 resync，不抛异常——抓包里的脏数据不该打断整条流。

    缓冲只保留凑不满一帧的尾巴，任何时刻都不超过 max_frame_size。
    """

    def __init__(self, max_frame_size=MAX_FRAME_SIZE):
        self.max_frame_size = max_frame_size
        self._buf = bytearray()
        self.offset = 0
        self.records = 0
        self.frames = 0
        self.errors = []
        self._next_frame_index = 0
        self._pending_error = None

    @property
    def pending(self):
        return len(self._buf)

    def feed(self, chunk):
        """喂一块字节，返回本次解出的 Record/Frame 列表。"""
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise TypeError("chunk 需要字节串，收到 %r" % (type(chunk).__name__,))
        self._buf += chunk
        if self._pending_error is not None:
            self._resync()
        out = []
        self._drain(out)
        return out

    def _resync(self):
        """上一次坏帧之后：丢掉缓冲，直到撞上新的 0x81 帧头。"""
        idx = self._buf.find(_MAGIC_BYTE)
        if idx < 0:
            self.offset += len(self._buf)
            del self._buf[:]
            return
        self._pending_error.resync_at = self.offset + idx
        self.errors.append(self._pending_error)
        self._pending_error = None
        if idx:
            del self._buf[:idx]
            self.offset += idx

    def _drain(self, out):
        buf = self._buf
        pos = 0
        end = len(buf)
        max_size = self.max_frame_size
        while pos < end:
            if buf[pos] == FRAME_MAGIC:
                try:
                    frame, next_pos = _frame_at(buf, pos, end, max_size)
                except _NeedMore:
                    break
                except DecodeError as exc:
                    pos = self._item_error(exc, buf, pos, end, is_frame=True)
                    continue
                out.append(frame)
                self.frames += 1
                self._next_frame_index += 1
                pos = next_pos
            else:
                if end - pos < RECORD_SIZE:
                    break
                try:
                    record, _ = unpack_record(buf, pos)
                except DecodeError as exc:
                    pos = self._item_error(exc, buf, pos, end, is_frame=False)
                    continue
                out.append(record)
                self.records += 1
                pos += RECORD_SIZE
        if pos:
            del buf[:pos]
            self.offset += pos

    def _item_error(self, exc, buf, pos, end, is_frame):
        """解析失败不计入输出：记一条错误，返回 resync 后的缓冲位置。"""
        message = exc.args[0] if exc.args else "解码失败"
        if is_frame:
            frame_index = self._next_frame_index
            self._next_frame_index += 1
        else:
            frame_index = None
        err = FrameDecodeError(message, offset=self.offset + pos,
                               field=exc.field,
                               frame_index=frame_index)
        idx = buf.find(_MAGIC_BYTE, pos + 1)
        if idx < 0:
            self._pending_error = err
            return end
        err.resync_at = self.offset + idx
        self.errors.append(err)
        return idx

    def finish(self):
        """流已经到末尾：没解完的坏帧和截断帧都记进 errors。"""
        if self._pending_error is not None:
            self._pending_error.resync_at = self.offset
            self.errors.append(self._pending_error)
            self._pending_error = None
        if not self._buf:
            return []
        if self._buf[0] == FRAME_MAGIC:
            try:
                _frame_at(self._buf, 0, len(self._buf), self.max_frame_size)
            except _NeedMore as exc:
                self.errors.append(FrameDecodeError(
                    "帧被截断: 字段 %s 未收齐" % exc.field,
                    offset=self.offset, field=exc.field,
                    frame_index=self._next_frame_index,
                    resync_at=self.offset + len(self._buf)))
            except DecodeError as exc:
                self.errors.append(FrameDecodeError(
                    exc.args[0] if exc.args else "帧解码失败",
                    offset=self.offset, field=exc.field,
                    frame_index=self._next_frame_index,
                    resync_at=self.offset + len(self._buf)))
            self._next_frame_index += 1
            self.offset += len(self._buf)
            del self._buf[:]
            return []
        self.errors.append(FrameDecodeError(
            "流末残留 %d 字节，记录被截断" % (len(self._buf),),
            offset=self.offset, field="record", frame_index=None,
            resync_at=self.offset + len(self._buf)))
        self.offset += len(self._buf)
        del self._buf[:]
        return []

    def __repr__(self):
        return "FrameDecoder(offset=%d, records=%d, frames=%d, errors=%d, pending=%d)" % (
            self.offset, self.records, self.frames,
            len(self.errors), len(self._buf))
