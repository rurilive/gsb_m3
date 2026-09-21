# fwkit

自研的防火墙规则集匹配包,纯标准库,地址网段用 `ipaddress` 处理。

## 现状

`fwkit/rules.py` 提供 `Packet`、`Rule` 和文本解析:

- 规则一行一条:`[prio=<int>] <action> <src> <dst> <ports>`,action 取 `allow` 或 `deny`,src 和 dst 是 CIDR 或 `any`,ports 是 `any`、单端口或 `lo-hi` 闭区间;空行与 `#` 注释跳过
- `Rule.parse(text, line_no)` 单行解析,`parse_rules(lines)` 整段解析并带上文本行号;`Rule.matches(packet)` 判断包是否落在选择器里,地址族不同一律不算命中
- `Rule.selector()` 返回归一化后的 (src, dst, port_lo, port_hi),可以用来比较两条规则是不是同一组条件

`fwkit/matcher.py` 提供 `RuleSet`:

- 规则按 `prio` 升序、同 `prio` 按加入先后参与匹配,先命中先算;没命中走可配的默认策略(构造 `default_action=` 或 `default_action(action)` 运行时切换,`allow` / `deny` 均可)
- 构造可带规则文本;`reload(lines)` 整体重载,`add_rule` / `remove_rule(line_no)` 热更新,都立即生效;`reload` 先解析构建完再原子切换,失败时旧表不动
- `match(packet)` 返回 `MatchResult(action, rule)`;没命中时 `rule` 为 `None`
- `rules()` / `line_numbers()` 按匹配顺序看当前规则集,`stats()` 看 `MatchStats`
- `diagnose()` 返回 `Diagnosis`:`redundant` 是被前面规则整个包住、动作相同的冗余项,`unreachable` 是被包住却动作相反的不可达项,均为带双方行号的 `ShadowFinding(coverer, rule)`

`fwkit/stats.py` 里的 `MatchStats` 记 `lookups`、`comparisons`(每次匹配拿包试了多少条规则)、`matched`、`fell_through`、`reloads`。

## 实现说明

1. 匹配顺序为 `(prio, 加入序号)` 升序,`match` 先命中先算,全落空才走默认策略。
2. 索引按 v4/v6 分族,族内是 (src 前缀, dst 前缀) 的 tuple-space:exact、src-any、dst-any 三类 cell,both-any 单独存。
3. 每个 cell 内把端口区间规范分解成 2 的幂对齐块(段树);匹配沿端口的树路径取候选,桶按 `(prio, seq)` 有序并归并。
4. 一次匹配只探测包地址实际所属前缀的 cell(plen 笛卡尔积上做点查),试到的规则数只取决于前缀区分度,不随规则总量线性涨。
5. 跨地址族:exact 规则按 (src 族, dst 族) 四组分表,跨族包只查对应组合表(如 v4→v6 只查 `(4,6)`),配合两张半边表,跨族绝不误命中。
6. `diagnose()` 用同样的索引按“更短前缀 + 端口路径”枚举可能的覆盖者,再用网段 `subnet_of` 与端口包含精确判定,不漏报不误报;每条规则只挂最早盖住它的规则。
7. 增删后整体重建索引并原子替换内部引擎;`reload` 先解析、构建离线视图,成功才切换并计数,语法错误时线上规则集原封不动,没有半装或放行空窗。
8. 所有读写在同一把可重入锁下;统计口径不变,`comparisons` 仍只对真正拿包试过的规则计数。

## 运行

```bash
python3 demo.py                             # 匹配与热更新演示
python3 -m unittest discover -s tests -v    # 基线 + 本轮验收测试
```
