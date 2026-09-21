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

新词法已落地：`cmdparse/lexer.py` 的 `tokenize(text)` 取代“按空白硬切”，
`cmdparse/quote.py` 的 `quote_word(text)` 管规范引用。约束：

- 现有行为与 `tests/` 下的基线保持不变（基线一个字不改）
- 纯标准库（`re`、`collections`、`unittest` 等在，装不了三方包），
  运行环境没有网络
- 坐标口径沿用 `diagnostics.py` 的约定：1 起算、按码点数

## 新词法

`cmdparse/lexer.py`：

- `tokenize(text)` 返回 `Token` 列表。`Token` 带转义还原后的 `text`，
  以及原文起止行列 `start_line/start_column/end_line/end_column`
  （均 1 起算、末尾开区间），`source_slice(source)` 能从原文切回原始字符，
  含引号、反斜杠与续行换行，直接给高亮用
- 认单引号（内部全字面）、双引号（`\"`、`\\`、`\$`、`` \` `` 转义，
  其余反斜杠原样留着，`$HOME`、`${X}` 这类变量占位符不被吃）、
  词外反斜杠转义、`#` 行内注释（只认词首）、行尾反斜杠续行
  （引号内外都消换行）；空引号是活下来的空词
- 未闭合引号、悬空转义抛 `diagnostics.ParseError`，行列指到源头
  （引号错误指开引号，转义错误指反斜杠），`format()` 照旧渲染脱字符
- 收 `str`，也收 `bytes`（UTF-8 宽松解码，乱码变 `\ufffd`），
  其余类型抛 `TypeError`；不崩不卡，输出只有词素或 `ParseError`

`CommandDocument.tokens()` 在整块文档上跑新词法，按词素起点行分组，
空行跳过，跨续行/跨行的词归在起点行；老的 `commands()` 等方法原样未动。

`cmdparse/quote.py`：

- `quote_word(text)` 输出与 `shlex.quote` 同口径：空串给 `''`，
  安全词原样，其余套单引号（词内单引号拆成 `'"'"'`）
- 往返保证：`tokenize(" ".join(quote_word(w) for w in words))`
  逐词还原，空串也活得下来

### 与 shlex 的三处刻意差异

`tests/test_lexer.py` 的随机对拍只在两边对齐的生成域里逐词（并对报错）
比较，刻意避开下列三处按 shell 常理处理的分歧：

1. **行尾续行**：词外 `\` + 换行，shlex 当“转义换行”，词里留真实换行；
   本包按 shell 常理把换行消掉（`a\<NL>b` 得 `ab`），双引号内同样消掉。
2. **双引号内 `\$` / `` \` ``**：shlex 只认 `\"`、`\\`，会保留反斜杠
   （`"\$x"` 得 `\$x`）；本包按 shell 常理转义成字面 `$` / `` ` ``。
3. **词内 `#`**：`shlex.split(comments=True)` 把词内 `#` 也当注释起点
   （`a#b` 被注释）；shell 只认词首 `#`，本包里 `a#b` 是一个词。

其余细节（`\v`、`\f`、全角空格是普通字符；`\r` 算分隔符且占一列等）
与 shlex 默认 whitespace 口径一致。

### 性能

`python3 bench/perf_check.py` 实测：约 32 MB 命令流 9 秒级解析完
（要求 60 秒内），放大 8 倍耗时约 7.8 倍（要求不超 10 倍）。

## 运行

```bash
python3 demo.py                          # 老分词 + 新词法/引用/报错演示
python3 -m unittest discover -s tests -v # 全部行为测试（含随机对拍）
python3 bench/perf_check.py              # 32MB / 8x 性能验收
```
