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

- 新增 `pathmatch/ignore.py`：`IgnoreRules(text, base)` 解析一份 .gitignore，
  `matched(relpath, is_dir, rule_stack)` 在规则栈（根→深）上判定路径；`match` 未动。
- 解析：`#` 与空行跳过；`\` 转义 `#`、`!`、尾随空格；`!` 否定；尾 `/` 仅目录。
- 模式含 `/` 即锚定到 base，否则匹配任意层级同名；`**` 跨段（`**/`、`/**`、`/**/`）。
- 判定自根向深逐层走查路径前缀：父目录被忽略即终止（其下无法重新包含）；
  同层内深层规则文件优先、文件内后写优先；无命中返回 `('allowed', None)`。
