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

- `pathmatch/ignore.py` 新增 `IgnoreRules(text, base)` 与 `matched(relpath, is_dir, rule_stack)`，不改动 `match`。
- 解析：`#`/空行注释，`\` 转义 `#`、`!`、尾随空格；`!` 否定；尾 `/` 目录限定。
- 模式含 `/` 锚定到 base，否则匹配任意层级同名路径；`**/`、`/**`、`/**/` 跨段。
- 每条规则编译成正则逐段匹配，段内 `*`/`?`/`[...]` 语义不变。
- `matched` 深层规则文件优先、同文件后写优先；路径无命中时逐级查父目录（视为目录）。
- 返回 `('ignored'|'allowed', 决定规则)`，无命中为 `('allowed', None)`。
