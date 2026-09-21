# wirepack

跟端上设备对接的二进制记录编解码库，纯标准库，无外部依赖。

## 线上格式

单条记录定长 16 字节，全部大端：

```
偏移  长度  字段
0     4     seq    无符号 32 位
4     1     kind   1=data, 2=ack, 3=ctrl
5     1     flags  保留位，原样透传
6     10    label  ASCII，右侧 NUL 补齐
```

`seq` 由上游位点分配器发放，约定不超过 800 万，编解码两端都按这个前提做校验：
写的时候超范围直接拒掉，读的时候超出范围按错位处理。

## 新帧格式

新设备改发变长帧，`0x81` 打头，整数一律 LEB128（单个 varint 最多 5 字节）：

```
字段        类型      说明
magic       1 字节    固定 0x81（老记录首字节是 seq 高字节 <= 0x7A，不会撞）
tag         varint    最低位=1 表示 payload 里再套了一层帧
payload_len varint    负载长度前缀
payload     字节串    长 payload_len
ext_count   varint    ext 条目数
ext 条目    key varint + value_len varint + value 字节串
```

整帧总长（含 magic）不得超过 `MAX_FRAME_SIZE`（64 KiB）。老设备还发老记录，
两种混在一条流里，`FrameDecoder` 按首字节自己区分。

## 模块

- `wirepack/errors.py`：`WireError` 基类，`EncodeError` 与 `DecodeError`；
  解析异常带 `offset`（流内字节偏移）和 `field`（字段名）；
  `FrameDecodeError` 额外带 `frame_index` 与 `resync_at`
- `wirepack/records.py`：`Record` 模型，`pack_record()` / `unpack_record()`，
  `MAX_SEQ`、`RECORD_SIZE`、`encode_label()` / `decode_label()`
- `wirepack/frame.py`：`Frame` 模型，`pack_frame()` / `unpack_frame()`，
  `FRAME_MAGIC`、`MAX_FRAME_SIZE`、`encode_varint()`
- `wirepack/stream.py`：`RecordStream` 按块喂入（`feed()` 吃任意切分的字节块，
  `offset`、`pending` 反映消费与缓冲字节数，`finish()` 校验流末），
  另有 `iter_records()` 与切片工具 `chunked()`；
  `FrameDecoder` 解新老混流，`feed()` 返回 Record/Frame 混合列表

`FrameDecoder` 的容错口径：新帧解失败（长度前缀超上限、varint 超 5 字节、
帧被截断）不抛异常，错误记进 `errors`（带 `frame_index`/`field`/`resync_at`），
解码器跳到下一个 `0x81` 帧头继续解；老记录解失败同样记进 `errors`
（`frame_index` 为 None）并 resync，抓包里的脏数据不会打断整条流。
缓冲只保留凑不满一帧的尾巴，不超过 `MAX_FRAME_SIZE`。

流式解码只保留凑不满一条记录的尾巴，解析过的字节马上丢掉，内存不随流长增长。

## 运行

```bash
python3 demo.py                           # 记录与新帧布局、混流喂入、吞吐、脏数据 resync
python3 -m unittest discover -s tests -v  # 既有行为基线测试
```

## 约定

`tests/` 下的用例锁的是现有线上行为，改动前先跑一遍；
`RecordStream` 的行为（偏移口径、错位检测、流末校验）是对外的接口约定。
