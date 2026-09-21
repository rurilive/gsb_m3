# fwkit

自研的防火墙规则集匹配包,纯标准库,地址网段用 `ipaddress` 处理。

## 现状

`fwkit/rules.py` 提供 `Packet`、`Rule` 和文本解析:

- 规则一行一条:`[prio=<int>] <action> <src> <dst> <ports>`,action 取 `allow` 或 `deny`,src 和 dst 是 CIDR 或 `any`,ports 是 `any`、单端口或 `lo-hi` 闭区间;空行与 `#` 注释跳过
- `Rule.parse(text, line_no)` 单行解析,`parse_rules(lines)` 整段解析并带上文本行号;`Rule.matches(packet)` 判断包是否落在选择器里,地址族不同一律不算命中
- `Rule.selector()` 返回归一化后的 (src, dst, port_lo, port_hi),可以用来比较两条规则是不是同一组条件

`fwkit/matcher.py` 提供 `RuleSet`:

- 构造可带规则文本;`reload(lines)` 整体重载,`add_rule` / `remove_rule(line_no)` 热更新,都立即生效
- `match(packet)` 按加入顺序逐条试,第一条命中的规则说了算,返回 `MatchResult(action, rule)`;没命中时 `rule` 为 `None`
- `rules()` / `line_numbers()` 看当前规则集,`stats()` 看 `MatchStats`

`fwkit/stats.py` 里的 `MatchStats` 记 `lookups`、`comparisons`(每次匹配拿包试了多少条规则)、`matched`、`fell_through`、`reloads`。

## 问题

规则一多就顶不住:`match` 是逐条线性扫描,十万条规则时单次判决要挨个试;每条规则的 `prio` 解析了却没人用,匹配顺序就是加入顺序;加载时也不检查规则之间的关系,被前面规则完全盖住的冗余项、盖住却动作相反的不可达项都静静躺在表里;没命中时固定落到 `deny`,没得配;`reload` 先清空再逐条装,中途的规则集是不完整的。

## 目标

见任务描述。约束:

- `tests/test_ruleset.py` 基线一个字不改,必须原样全绿
- 纯标准库,不引三方包

## 运行

```bash
python3 demo.py                             # 匹配与热更新演示
python3 -m unittest discover -s tests -v    # 行为基线测试
```
