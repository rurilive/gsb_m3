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

- `pathmatch/ignore.py` 提供 `IgnoreRules(text, base)`、`Rule` 与 `matched(relpath, is_dir, rule_stack)`。
- `#` 与空行为注释；`\#`、`\!`、`\␠` 转义；行首 `!` 否定，尾 `/` 仅目录，含 `/` 锚定，无 `/` 匹配任意层级。
- `**` 跨段：`**/foo` 任意层、`foo/**` 匹配目录全部内容（不含自身）、`a/**/b` 零或多层。
- `matched` 逐层收集目标及祖先目录上的命中，按命中层级→规则集合深度→行号取决定规则，深者优先、后匹配优先。
- 父目录一旦被非否定规则排除，其内部的规则集合不再生效（与 git“不可再包含已排除父目录的子代”一致）。
- 返回 `('ignored'|'allowed', Rule)`，无命中为 `('allowed', None)`；规则集合在 `rule_stack` 中的顺序不影响结果。
