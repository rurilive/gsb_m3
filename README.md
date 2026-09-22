# mailnorm

邮件网关里的小解析器，把邮件文本拆成头部表与正文。纯标准库，运行环境没有
网络，装不了三方包。

## 现状

`mailnorm/errors.py` 定义 `MailParseError`，错误带字符偏移与行号。

`mailnorm/headers.py` 管头部块：

- `split_header_lines(block)` 把头部块拆成 `(name, value)` 列表，值去首尾
  空白；抬头是空白的续行还没支持，会按没有冒号的行报错
- `parse_headers(block)` 出 `Headers`，按名字取值不区分大小写，`get` /
  `get_all` / `names` / `items` 都在
- `split_addresses(value)` 按逗号把地址列表切开，只做简单去空白

`mailnorm/mime.py` 管 MIME 零碎：

- `parse_content_type(value)` 拆主类型与参数，参数按分号硬切、值剥外层引号
- `decode_transfer(payload, encoding)` 只认 7bit / 8bit / binary 这类不动
  内容的编码，原样返回字符串

`mailnorm/message.py` 是组装层：

- `split_message(text)` 按第一个空行切出头部块与正文，给出正文偏移
- `Message.parse(text)` 出 `Message`：`headers`、`body`、`content_type`、
  `params`，`is_multipart()` 只判断出 multipart 这种主类型
- `Message.text()` 给单段 us-ascii 文本邮件的正文

## 目标

见任务描述。约束：

- `tests/` 下的基线测试一个字不改，必须保持全绿
- 纯标准库（`base64`、`quopri`、`codecs` 等在，装不了三方包），核心逻辑
  不许直接调 `email` 包的解析器，测试里拿它当参照可以
- `python3 demo.py` 必须能直接跑

## 运行

```bash
python3 demo.py                          # 各模块现有能力走一遍
python3 -m unittest discover -s tests    # 基线测试
```
