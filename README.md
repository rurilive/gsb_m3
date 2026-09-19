# framec

链路层二进制帧编解码：注册表驱动 + CRC 校验管线。单进程内嵌，纯标准库，无外部依赖。

## 模块结构

- `framec/registry.py`：线格式常量（MAGIC / MAX_PAYLOAD / HEADER_LEN / CRC_LEN）、`FrameType` 基类与 `REGISTRY`。新增帧类型继承 `FrameType`、实现 `encode`/`decode`（按需覆写 `validate`），调 `register()` 即可，编解码核心不用动；类型码冲突抛 `FrameError`
- `framec/types.py`：内置帧类型 DATA / JSON / ACK（类型码 0x01-0x03），模块导入即注册
- `framec/codec.py`：`Encoder`（seq 自增打帧，ftype 可传实例/类/已注册类型码；缺省按值类型推断 str→DATA、dict→JSON）与 `Decoder.feed`（增量解码，数据可任意切分，凑齐整帧才输出）
- `framec/errors.py`：`FrameError` 基类及 HeaderError / CrcError / UnknownTypeError / PayloadError

## 线格式与容错语义

多字节字段统一大端：
`magic(2)=b"FC" | type(1) | flags(1)=保留必须 0 | length(2) | seq(4) | payload(length) | crc32(4)`，
CRC 覆盖从 magic 到 payload 的全部字节。

`Decoder.feed` 容错：帧头非法（magic 不匹配 / 保留位非 0 / 声明长度超上限）抛
`HeaderError` 且不消费缓冲；CRC 失败抛 `CrcError`，该帧字节已消费、流可继续；
类型码未注册的帧静默跳过（前向兼容）；载荷校验或解码失败抛 `PayloadError`，
该帧字节已消费。`Encoder.encode` 侧超长或编码失败同样抛 `PayloadError`。

## 运行

```bash
python3 demo.py                          # 组帧、跨包解码、CRC 容错演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

`tests/test_framec.py` 是现有行为的锁定基线。
