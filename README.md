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

## 运行

```bash
python3 demo.py                          # 现状演示：切词、统计、拒收报错
python3 -m unittest discover -s tests -v # 行为基线测试
```
