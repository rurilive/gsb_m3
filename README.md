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
  .gitignore 文件；`matched(relpath, is_dir, rule_stack)` 逐层判定，
  返回 `('ignored'|'allowed', 决定规则)`，无命中为 `('allowed', None)`。
- 解析：空行与 `#` 注释；`\` 转义 `#`、`!`、尾随空格；`!` 否定；
  尾 `/` 仅匹配目录；含 `/` 锚定 base，否则匹配任意层级同名路径；
  `**/`、`/**`、`/**/` 跨段，段内 `*`/`?`/`[...]` 语义不变。
- 判定：深层规则文件优先，同文件内后出现的规则优先；父目录被忽略
  则子路径不可恢复（与 git 一致）；决定规则上带有 base 与行号。
- `match` 及其测试未动；新能力全部为新增接口，纯标准库。
