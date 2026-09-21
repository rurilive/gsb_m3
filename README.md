# packwire

消息总线用的二进制编解码库，纯标准库，无第三方依赖。

## 现状

包分三层：

- `packwire/framing.py`：线格式的定长原语。当前格式里每个值以单字节类型码开头：
  - `TAG_INT`（0）：后跟 8 字节大端补码整数
  - `TAG_TEXT`（1）：后跟 4 字节大端字节长度，再跟 UTF-8 字节
  - `TAG_ARRAY`（2）：后跟 4 字节大端元素个数，再跟逐个元素的编码
- `packwire/codec.py`：`encode(obj) -> bytes` 与 `decode(data) -> obj`，
  支持 int、str、list，可任意嵌套；布尔按整数处理，解码结果都是普通 Python 值
- `packwire/errors.py`：`PackError` 是基类，`EncodeError` 报编码问题，
  `DecodeError` 报解码问题并带 `offset` 属性

错误与偏移约定：认不出的类型码、坏 UTF-8、输入中途截断、尾部有多余字节，
都报 `DecodeError`；`offset` 指向第一个出问题的字节，输入提前耗尽时指向输入长度，
也就是下一个本该出现却没有的字节。

当前格式的好处是简单，代价是不紧凑：每个整数固定 9 字节，每个字符串至少 5 字节开销。

## 目标

见任务描述。约束：

- `tests/` 下现有测试一字不改，必须保持全绿
- 纯标准库，不引入三方依赖

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
