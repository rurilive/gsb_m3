# linkmux

跟采集端之间的单连接链路库，纯标准库、无外部依赖。传输层是内存里的
两端 Endpoint，发送即进对端收件箱，时钟可注入（ManualClock 手动推进）。

## 线上格式

帧 = 8 字节定长头 + 负载，全部大端：

```
偏移  长度  字段
0     4     stream_id  0 号留给连接级帧
4     1     kind       1=data, 2=window_update, 3=fin, 4=reset, 5=ping
5     1     flags      保留位，原样透传
6     2     length     负载字节数，上限 MAX_FRAME_PAYLOAD（1024）
```

约定：`data` 帧的负载是这条流的净荷，写端按 `frame_limit` 自己切分；
`fin` / `reset` 不带负载；`window_update` 的负载固定 4 字节大端无符号，
是给对端这条流补的接收额度；流号从 1 起、步长 2，client 角色发起的流占
奇数号，server 角色占偶数号；头部 length 超上限时解码器只看头就报错。

## 模块与运行

`errors.py` 是异常层次；`frame.py` 管帧的编解码与拆帧（`Frame`、
`pack_frame()` / `unpack_frame()`、`pack_window()` / `unpack_window()`、
按块喂入的 `FrameBuffer`）；`transport.py` 是内存连接（`MemoryLink.pair()`
建一对 `Endpoint`，`SystemClock` / `ManualClock`）；`session.py` 是串行的
`Session` 和把两端泵到安静的 `pump_all()`。

```bash
python3 demo.py                           # 帧布局、串行往返、分片、延迟、重置
python3 -m unittest discover -s tests -v  # 既有行为基线测试
```

`tests/` 下的用例锁的是线上现有行为：帧格式、串行 `Session` 的语义
（一次一对、流号步长、分片口径、reset 的表现）都是对外的接口约定，
改动前先跑一遍。`Session` 一次只跑一对请求响应，采集端的多路数据
目前只能在应用层排队。
