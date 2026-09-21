# cmdparse

部署面板背后的命令流解析小包，纯标准库，无外部依赖。

## 现状

`cmdparse/tokenizer.py` 是最初那版切分：

- `split_words(text)` 按空白连续段切词，保持出现顺序，空串与纯空白给空列表
- 空白按 Python 正则 `\s` 的口径，引号、反斜杠、井号都只是普通字符
- 只认 `str`，其余类型抛 `TypeError`

`cmdparse/document.py` 提供 `CommandDocument`：

- 构造时只认 `str`，整块内容先查一遍 NUL 字节，有就拒收
- `line_count()` / `line(n)` / `iter_lines()` 按 `\n` 切行，行号 1 起算，
  末尾换行会切出一个空行，不做特判
- `commands()` 逐行切词、空行跳过，给 `(行号, 词列表)`；`word_count()` 给全篇词数

`cmdparse/diagnostics.py` 管坐标与报错：

- `ParseError(message, line, column, source_line)` 携带位置，
  `format()` 渲染成描述、源码行、脱字符三行；行列都 1 起算
- `render_caret(source_line, column, width=1)` 画脱字符行

`cmdparse/report.py` 是侧栏统计：`summarize(document)` 逐行报词数与合计，
`word_frequency(document, top=None)` 给词频，按次数降序、同频按词升序。

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 下的基线保持不变（基线一个字不改）
- 纯标准库（`re`、`collections`、`unittest` 等在，装不了三方包），
  运行环境没有网络
- 坐标口径沿用 `diagnostics.py` 的约定：1 起算、按码点数

## 新词法（2026-09）

面板命令输入框换成手写词法，老的空白切分原样保留、一个字没动：

- `cmdparse/lexer.py` 的 `tokenize(text)` 认单双引号、引号内外有别的
  反斜杠转义、词首行内注释（`#` 到行尾）、无引号行尾反斜杠续行；
  双引号里 `$GREETING`、`` `cmd` `` 这类变量/命令占位符原样保留。
  返回 `Token` 列表：每个词素带 `text`、`start`/`end`（`Position`：
  行、列、码点 offset，1 起算、末尾开）和 `segments`（`plain` /
  `single` / `double` 三段，供高亮区分引号内外）。未闭合引号指开引号、
  悬空转义指反斜杠，统一抛 `ParseError`。`str` 与 `bytes`/`bytearray`/
  bytes 视图都收，乱码按 UTF-8 `surrogateescape` 当普通字符，不崩不卡。
- `cmdparse/quote.py` 的 `quote_word(text)` 给规范引用：空串成 `''`，
  安全字符（ASCII 字母数字与 `@%+=:,./-`）原样，其余单引号包裹、
  内嵌单引号走 `'\''`；词素文本 `quote_word` 后用空格拼回再 `tokenize`，
  逐词一致（空串也活）。
- `CommandDocument.tokens()` 对整块文档走新词法（`commands()`、
  `split_words()` 等老方法不变）。

### 与 shlex posix 口径的对拍

`shlex` 只做随机语料对拍参照，不出词。对齐语料（约九万条随机命令行，
见 `tests/test_lexer.py`）逐词一致；刻意按 shell 常理点出的分歧有两处：

1. **无引号行尾续行**：`echo a\<换行>b`，shlex 得到 `['echo', 'a\nb']`
   （它不认续行，换行留在词里）；本词法得 `['echo', 'ab']`，与真实
   shell 一致。
2. **词中的 `#`**：`echo a#b`，shlex 从词中 `#` 起注释掉整行，得
   `['echo', 'a']`；本词法按 bash 常理只在词首（行首或空白后）起注释，
   得 `['echo', 'a#b']`。

另外几处只影响形式、不影响词文本：shlex 对未闭合引号/悬空转义抛
`ValueError` 且不带行列，这里抛 `ParseError` 并指向源头字符；`shlex`
不收 `bytes`，这里收；`shlex` 不给原文区间，这里每个词素和分段都给。

性能：32 MB 模拟命令流（约四百万词素）在本机 15 秒上下解析完；放大
八倍（256 MB）耗时放大约 8.4 倍，线性、不超十倍。坐标按需换算，不看
区间时扫描不为坐标建对象。

## 运行

```bash
python3 demo.py                          # 现状演示：切词、统计、拒收报错
python3 demo.py                          # 末尾三段：新词法词素/坐标、报错、往返
python3 -m unittest discover -s tests -v # 行为基线测试
```
