# chunkmime

按块喂入的 multipart/form-data 解析器,纯标准库,无外部依赖。

## 用法

上传网关收到多少字节就往后端喂多少,解析器边收边把字段和文件内容
交出去:

```python
from chunkmime import MultipartParser, PartCollector

collector = PartCollector()
parser = MultipartParser(boundary, collector)
for chunk in chunks:
    parser.feed(chunk)
parser.finish()
for part in collector.parts():
    print(part.name, part.filename, len(part.data))
```

- `MultipartParser(boundary, sink=None)`:boundary 是 Content-Type 里的
  边界串,str 或 bytes 都行。`feed(chunk)` 喂任意大小的块,`finish()`
  在流结束后收尾
- sink 是结果的接收端,要有 `begin_part(headers, params)`、`write(data)`、
  `end_part()` 三个方法:
  - `PartCollector`:把正文收进内存,`parts()` 取 `Part` 列表
  - `DiscardSink`:只记账(部分数、字节数、字段名),大文件或压测时用
- `Part` 上有 `headers`、`params`、`data`,还有 `name` 和 `filename`
  两个快捷属性,取自 Content-Disposition 的参数

## 语义约定

- 分隔行按 CRLF 换行;收尾分隔行之后的 epilogue 忽略,第一个分隔行
  之前的 preamble 也忽略
- 正文不包含分隔行前那个 CRLF,也不包含部分头部后面的结束空行
- 正文里出现和分隔行长得像的字节时,按规范那一截不算分隔行
- `chunkmime/reference.py` 的 `parse_all(body, boundary)` 把整份 body
  一次切完,是语义基准,给测试对拍用;增量实现切出来的东西要和它
  一致,结构不完整的输入两边都要报 `ParseError`

## 运行

```bash
python3 demo.py                          # 修复后行为演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 修复说明

线上真实上传翻车后,`chunkmime/parser.py` 的状态机重写、
`chunkmime/headers.py` 的参数解析对齐了 `reference.py`,修掉的点:

- 正文里出现分隔行的半截前缀、且切点正好落在那一截后面时,旧逻辑
  会把前缀当成真分隔行并跳字节,内容从那儿被切开丢一截。新逻辑只把
  marker 长度量级的后缀留在解析器里,等下一块拿到「marker 后面两个
  字节」再定性:必须是 `--` 或 `CRLF` 才算分隔行,否则前缀原样补回
  sink;分隔行(含收尾的 `--`)被切在块边界的任意位置都不再丢字段。
- 完整 marker 后面跟其他字节(`--abc123X` 这类)按规范只是正文,
  旧逻辑会误判;现在和 `reference._find_marker` 一样继续往后找。
- 头部块跨块时旧逻辑找的是 `\n\r\n`,头部值会多出一个尾随回车;
  现在统一按 `CRLF CRLF` 找结束空行,与切块位置无关。
- `parse_params` 不再用正则:双引号值里的反斜杠转义会还原
  (`\"` -> `"`、`\\` -> `\`),值按头部本来的 latin-1 原文返回、
  不做多余的 strip 和 UTF-8 替换,语义与 reference 完全一致。
- `finish()` 收到不完整的流(没见到收尾分隔行、头部没收完、开场
  分隔行残缺等)一律抛 `ParseError`,不再静默当成功;收尾 `--`
  之后的 epilogue 缺不缺都不影响成功。

解析器手里只留跨块待定的字节(上限约一个分隔行 + 2 字节)和当前
头部块,正文按块直通 sink、不按字节循环。`tests/test_streaming_fixes.py`
覆盖了定点回归、逐偏移 + 随机切块对拍、随机截断报错,以及 50MB
正文的内存/计时(64KiB 块约 0.7s、解析器峰值约 0.3MB,远低于
8MB / 10s 的验收线)。跑全部测试:

```bash
python3 -m unittest discover -s tests -v
```
