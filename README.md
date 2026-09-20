# httpparse

内部网关的 HTTP/1.1 请求解析：请求行 + 头部 + Content-Length / chunked body，一口气吃完整个请求再返回。2018 年上线，纯标准库，无外部依赖。

## 对外 API（不可变更）

- `parse_request(data: bytes) -> HttpRequest`
- `HttpRequest`：属性 `method` / `target` / `version`（str）、`headers`（`[(name, value)]`，原始大小写、出现顺序）、`body`（bytes）；方法 `header(name, default=None)`（大小写不敏感，取第一个匹配）
- `ParseError(ValueError)`：请求不合法时抛出

## 契约口径（历史形成，全部要保住）

- 行结束符 `\r\n` 与裸 `\n` 都认；行长度上限按含换行符的整行字节数算，8192
- obs-fold 折行头续上一条的值；头名字不做字符校验（带空格照收）；值里控制字符非法（tab 除外）
- 没有 CL/TE 时 body 为空，头部后的剩余字节忽略；TE chunked 优先于 CL；trailer 收下但不进 headers
- method 只收大写字母和连字符；version 须为 `HTTP/主.次` 数字
- 全部错误文本以 `tests/test_http.py` 为准（下游日志采集在正则匹配）

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- `constants.py`：全部历史口径常量——行长上限 8192、CR/LF、空格/tab、`HTTP/` 前缀等，别处不再出现字节魔法数
- `tokenizer.py`：只做字节层的事，维护增量缓冲，按 LF 切行并剥行尾 CR，行长限制（含 CR 的整行口径）在这一层强制
- `message.py`：HTTP 语义层，`RequestReader` 按 请求行 → 头部 → chunked/CL body 显式状态推进，`ParseError` 与全部错误文本都在这层
- `parser.py`：对外门面，三个公开对象签名不变；`parse_request` 只是把数据一次 feed 完再 finish 的薄封装
- 状态推进在 `RequestReader._pump`：每个状态处理器返回“数据不够”即停在原处，残缺行/半截 body 留在 tokenizer 缓冲里
- 接得住流式是因为没有“一口气吃完”假设：数据可以任意分段 `feed`，凑够一行或够 N 字节才前进，`finish()` 再按历史口径对截断报错
