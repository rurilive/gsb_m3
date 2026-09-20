# texttbl

文本表格渲染器：列对齐、超长自动换行、四套边框样式。监控后台和 CLI 工具在用，2019 年上线，纯标准库，无外部依赖。

## 对外 API（不可变更）

- `Table(headers, style="ascii", wrap=0)`
  - `headers`：列名列表（非字符串会 str() 转换）
  - `style`：`ascii` / `light` / `heavy` / `markdown`
  - `wrap`：单元格换行宽度（0 或负数 = 不换行）
- `add_row(*cells) -> Table`：格子数可比列少（缺的当空串渲染），比列多抛 ValueError
- `render() -> str`：整表文本，不带尾换行

## 契约口径（历史形成，全部要保住）

- 列宽 = 全表（含表头）按显示宽取最大，左对齐右侧补空格
- 显示宽度按 len() 算，中文等宽字符也按 1 个宽
- 换行按词贪心（连续空白算一个分隔），超长词先清行再硬切；表头同样参与换行
- markdown 分隔行横线数与列宽一致；空表不画数据分隔线
- 各样式的逐字节输出以 `tests/test_table.py` 为准

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- `texttbl/model.py`：`Cell` 存原始内容 + 换行后的行块（行高 = `len(lines)`）；`Column` 是一列的纵向视图，列宽作为数据挂在上面；`build_grid`/`build_columns` 负责从行列数据建模型。
- `texttbl/width.py`：宽度纯函数 `text_width`（按 len 的历史口径）和换行 `wrap_text`；模块级 `_WIDTH_CACHE` 只由 `text_width` 读写，别处不碰。
- `texttbl/styles.py`：样式表 `STYLES`，每套样式是一个 `BorderStyle`（vert/horiz + top/mid/bot 三元组，markdown 只置标志位）；加样式 = 加一条数据。
- `texttbl/render.py`：统一管线——建模型 → 取样式 → `_assemble` 拼装（横线、行块、markdown 分隔各一个函数），`Table` 对外 API 不变。
