# pathmatch

构建系统的路径匹配模块，单进程内嵌，纯标准库，无外部依赖。

## 现状

`pathmatch/match.py` 提供 `match(pattern, path)`：两侧按 `/` 分段、
段数一致且逐段命中才算匹配。`*` 匹配段内任意字符（不跨段），
`?` 匹配段内单个字符，其余字符按字面，大小写敏感。

## 问题

扫描源码树时要按 .gitignore 风格的规则排除生成物：否定、目录限定、
根锚定、跨段通配、嵌套规则文件优先——这些段级 glob 都表达不了，
硬拼出来的 pattern 又脆又难维护。

## 约定

- `match` 的现有行为不变（`tests/test_match.py` 是行为基线，一个字不改）
- 新能力以新增接口提供，不改现有函数签名
- 纯标准库

## 运行

```bash
python3 demo.py                          # 段级 glob 演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 新接口在 `pathmatch/ignore.py`：`IgnoreRules(text, base)` 解析一个
  .gitignore 文件，`base` 为其所在目录相对根的前缀；`matched(relpath,
  is_dir, rule_stack)` 在规则栈（浅->深）上判定，返回
  `('ignored'|'allowed', 决定规则)`，无命中为 `('allowed', None)`。
- 解析：`#` 与空行跳过，`\` 转义 `#`、`!`、尾随空格；`!` 否定；
  尾 `/` 仅匹配目录；含 `/` 的模式锚定到 base，否则按任意层级同名匹配。
- `**` 作独立段跨段：前缀任意层、后缀全部、中间零或多层；段内仍
  `*`/`?`/字符类，大小写敏感。
- 判定顺序：深层文件优先，同文件内后面的规则优先；祖先目录被忽略则
  路径直接 ignored（与 git 一致，其下内容无法被否定规则重新包含）。
