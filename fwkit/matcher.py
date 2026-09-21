"""规则集与匹配入口。

匹配顺序:规则按 priority 升序排,同 priority 按加入先后,先命中先算;
全部落空才走默认策略(默认 deny,构造时可配成 allow)。

为避免逐条线性扫描,内部按地址族(v4/v6)各维护一组 tuple-space 索引:
(src 前缀, dst 前缀)两个维度上,规则落在 exact / src-any / dst-any /
both-any 四类 cell;cell 内再用端口的规范区间分解树(区间切成若干 2 的幂
对齐块)。一次匹配只探测包地址真正所属前缀的 cell、沿端口树取候选,试到
的规则条数只取决于前缀区分度,不随规则总量线性涨。

跨地址族:src、dst 都是具体网段的规则按 (src 族, dst 族) 四组分表,
v4→v6 的跨族包只查 (4,6) 表;只有一边 any 的规则按具体一边的族分表;
both-any 规则单独存,任何族的包都会查到它。
"""

import bisect
import threading

from fwkit.rules import ACTIONS, ACTION_DENY, parse_rules
from fwkit.stats import MatchStats

# 没命中任何规则时的默认动作,RuleSet 构造时可以改。
DEFAULT_ACTION = ACTION_DENY

# 端口空间宽度,必须是 2 的幂,刚好盖住 0..65535。
_PORT_SPAN = 65536


class MatchResult:
    """一次匹配的结论:动作和命中的规则。

    没有规则命中时 rule 为 None,动作是默认策略。
    """

    __slots__ = ("action", "rule")

    def __init__(self, action, rule=None):
        self.action = action
        self.rule = rule

    @property
    def matched(self):
        return self.rule is not None

    def __eq__(self, other):
        if not isinstance(other, MatchResult):
            return NotImplemented
        return (self.action, self.rule) == (other.action, self.rule)

    def __repr__(self):
        return "MatchResult(action={!r}, rule={!r})".format(self.action, self.rule)


class ShadowFinding:
    """一条遮蔽关系:rule 被排在前面的 coverer 整个包住。

    kind 为 "redundant" 时双方动作相同,rule 永远没有独立判决;
    kind 为 "unreachable" 时双方动作相反,rule 被挡住且判决会被翻转。
    """

    __slots__ = ("kind", "coverer", "rule")

    def __init__(self, kind, coverer, rule):
        self.kind = kind
        self.coverer = coverer
        self.rule = rule

    def __eq__(self, other):
        if not isinstance(other, ShadowFinding):
            return NotImplemented
        return (self.kind, self.coverer, self.rule) == (
            other.kind, other.coverer, other.rule)

    def __repr__(self):
        return "ShadowFinding(kind={!r}, coverer=line {}, rule=line {})".format(
            self.kind, self.coverer.line_no, self.rule.line_no)


class Diagnosis:
    """diagnose() 的结论:冗余项与不可达项各一组 ShadowFinding。"""

    __slots__ = ("redundant", "unreachable")

    def __init__(self, redundant=(), unreachable=()):
        self.redundant = list(redundant)
        self.unreachable = list(unreachable)

    def __bool__(self):
        return bool(self.redundant or self.unreachable)

    def __eq__(self, other):
        if not isinstance(other, Diagnosis):
            return NotImplemented
        return (self.redundant, self.unreachable) == (
            other.redundant, other.unreachable)

    def __repr__(self):
        return "Diagnosis(redundant={}, unreachable={})".format(
            len(self.redundant), len(self.unreachable))


def _aligned_nodes(lo, hi):
    """把闭区间 [lo, hi] 规范分解成 (base, span),span 均为 2 的幂。

    任一端口在段树自顶向下的路径上,恰好经过包含它的全部区间块:
    不会漏,同一规则在路径上也不会出现两次。
    """
    end = hi + 1
    nodes = []
    while lo < end:
        span = _PORT_SPAN
        while span > 1 and (lo & (span - 1) or lo + span > end):
            span >>= 1
        nodes.append((lo, span))
        lo += span
    return nodes


def _family_bits(version):
    return 32 if version == 4 else 128


def _prefix_key(ip_value, version, prefixlen):
    """整数地址按前缀长度取网络位。"""
    if prefixlen == 0:
        return 0
    return ip_value & (((1 << _family_bits(version)) - 1)
                       << (_family_bits(version) - prefixlen))


def _covers(coverer, rule):
    """coverer 的选择器是否整个包住 rule。

    即任何匹配 rule 的包都匹配 coverer:src/dst 各自按网段包含判定,
    单边 any 不约束该侧;端口区间也必须整个包住。
    """
    if coverer.src is not None:
        if rule.src is None or rule.src.version != coverer.src.version:
            return False
        if not rule.src.subnet_of(coverer.src):
            return False
    if coverer.dst is not None:
        if rule.dst is None or rule.dst.version != coverer.dst.version:
            return False
        if not rule.dst.subnet_of(coverer.dst):
            return False
    return coverer.port_lo <= rule.port_lo and rule.port_hi <= coverer.port_hi


def _merge_streams(streams):
    """把若干条各自按 (prio, seq) 有序、互不相交的 entry 流归并。"""
    streams.sort(key=len)
    merged = list(streams[0])
    for stream in streams[1:]:
        combined = []
        i = j = 0
        while i < len(merged) and j < len(stream):
            if (merged[i][0], merged[i][1]) <= (stream[j][0], stream[j][1]):
                combined.append(merged[i])
                i += 1
            else:
                combined.append(stream[j])
                j += 1
        combined.extend(merged[i:])
        combined.extend(stream[j:])
        merged = combined
    return merged


def _tree_candidates(tree, port):
    """沿端口段树路径取所有 entry;桶内有序,这里做多路归并。"""
    span = _PORT_SPAN
    base = 0
    streams = []
    while True:
        bucket = tree.get((base, span))
        if bucket:
            streams.append(bucket)
        if span == 1:
            break
        span >>= 1
        if port & span:
            base += span
    if not streams:
        return ()
    if len(streams) == 1:
        return streams[0]
    return _merge_streams(streams)


class _Engine:
    """不可变匹配视图:规则顺序和索引一次性建好,更新时整体替换。

    entry 统一为 (priority, seq, rule),seq 是加入序号,同 prio 时决定
    先后。规则按 (src 族, dst 族) 组合分四张 exact 表;src 具体/dst any
    的半边规则放 dst_any[src 族],src any/dst 具体的放 src_any[dst 族],
    both-any 单独放 both_any_tree。于是 v4→v6 的跨族包只查
    exact[(4,6)]、dst_any[4]、src_any[6] 与 both-any,不会误命中他族
    具体前缀的规则。每个表内:前缀长度集合 + cell 字典 + 端口段树。
    """

    def __init__(self, entries, default_action):
        self.entries = sorted(entries, key=lambda item: (item[0], item[1]))
        self.default_action = default_action
        self.exact = {
            combo: {"plen_src": set(), "plen_dst": set(), "cells": {}}
            for combo in ((4, 4), (4, 6), (6, 4), (6, 6))}
        self.dst_any = {
            family: {"plen": set(), "cells": {}} for family in (4, 6)}
        self.src_any = {
            family: {"plen": set(), "cells": {}} for family in (4, 6)}
        self.both_any_tree = {}
        for entry in self.entries:
            self._index_entry(entry)

    def _insert_ports(self, tree, nodes, entry):
        for node in nodes:
            bucket = tree.get(node)
            if bucket is None:
                tree[node] = [entry]
            else:
                bisect.insort(bucket, entry)

    def _index_entry(self, entry):
        rule = entry[2]
        src, dst = rule.src, rule.dst
        nodes = _aligned_nodes(rule.port_lo, rule.port_hi)
        if src is not None and dst is not None:
            table = self.exact[(src.version, dst.version)]
            table["plen_src"].add(src.prefixlen)
            table["plen_dst"].add(dst.prefixlen)
            tree = table["cells"].setdefault(
                (int(src.network_address), int(dst.network_address)), {})
        elif src is not None:
            table = self.dst_any[src.version]
            table["plen"].add(src.prefixlen)
            tree = table["cells"].setdefault(int(src.network_address), {})
        elif dst is not None:
            table = self.src_any[dst.version]
            table["plen"].add(dst.prefixlen)
            tree = table["cells"].setdefault(int(dst.network_address), {})
        else:
            tree = self.both_any_tree
        self._insert_ports(tree, nodes, entry)

    # ---- 匹配 ----

    @staticmethod
    def _collect(streams, tree, port):
        found = _tree_candidates(tree, port)
        if found:
            streams.append(found)

    def _candidate_entries(self, packet):
        """选择器覆盖该包的全部 entry,按匹配顺序 (prio, seq) 归并。"""
        src_ip, dst_ip, port = packet.src, packet.dst, packet.port
        sf, df = src_ip.version, dst_ip.version
        src_int, dst_int = int(src_ip), int(dst_ip)
        streams = []

        exact = self.exact[(sf, df)]
        for src_plen in exact["plen_src"]:
            src_key = _prefix_key(src_int, sf, src_plen)
            for dst_plen in exact["plen_dst"]:
                tree = exact["cells"].get(
                    (src_key, _prefix_key(dst_int, df, dst_plen)))
                if tree is not None:
                    self._collect(streams, tree, port)

        dst_any = self.dst_any[sf]
        for plen in dst_any["plen"]:
            tree = dst_any["cells"].get(_prefix_key(src_int, sf, plen))
            if tree is not None:
                self._collect(streams, tree, port)

        src_any = self.src_any[df]
        for plen in src_any["plen"]:
            tree = src_any["cells"].get(_prefix_key(dst_int, df, plen))
            if tree is not None:
                self._collect(streams, tree, port)

        self._collect(streams, self.both_any_tree, port)
        if not streams:
            return ()
        if len(streams) == 1:
            return streams[0]
        return _merge_streams(streams)

    def match(self, packet, stats):
        stats.lookups += 1
        for _priority, _seq, rule in self._candidate_entries(packet):
            stats.comparisons += 1
            if rule.matches(packet):
                stats.matched += 1
                return MatchResult(rule.action, rule)
        stats.fell_through += 1
        return MatchResult(self.default_action, None)

    # ---- 遮蔽分析 ----

    def _coverer_candidates(self, rule):
        """枚举前缀与端口都可能盖住 rule 的 entry(候选超集)。

        覆盖者前缀必须不更长且网络位相同;端口只沿 rule.port_lo 的一条
        段树路径探测。是否真包住最终由 _covers 精确判定,不漏不误。
        """
        src, dst = rule.src, rule.dst
        port = rule.port_lo
        streams = []

        def from_table(table, src_plen_limit, dst_plen_limit,
                       src_int, src_version, dst_int, dst_version):
            for src_plen in table["plen_src"]:
                if src_plen > src_plen_limit:
                    continue
                src_key = _prefix_key(src_int, src_version, src_plen)
                for dst_plen in table["plen_dst"]:
                    if dst_plen > dst_plen_limit:
                        continue
                    tree = table["cells"].get(
                        (src_key,
                         _prefix_key(dst_int, dst_version, dst_plen)))
                    if tree is not None:
                        self._collect(streams, tree, port)

        if src is not None and dst is not None:
            from_table(
                self.exact[(src.version, dst.version)],
                src.prefixlen, dst.prefixlen,
                int(src.network_address), src.version,
                int(dst.network_address), dst.version)
            half = self.dst_any[src.version]
            for plen in half["plen"]:
                if plen <= src.prefixlen:
                    tree = half["cells"].get(
                        _prefix_key(int(src.network_address),
                                    src.version, plen))
                    if tree is not None:
                        self._collect(streams, tree, port)
            half = self.src_any[dst.version]
            for plen in half["plen"]:
                if plen <= dst.prefixlen:
                    tree = half["cells"].get(
                        _prefix_key(int(dst.network_address),
                                    dst.version, plen))
                    if tree is not None:
                        self._collect(streams, tree, port)
        elif src is not None:
            half = self.dst_any[src.version]
            for plen in half["plen"]:
                if plen <= src.prefixlen:
                    tree = half["cells"].get(
                        _prefix_key(int(src.network_address),
                                    src.version, plen))
                    if tree is not None:
                        self._collect(streams, tree, port)
        elif dst is not None:
            half = self.src_any[dst.version]
            for plen in half["plen"]:
                if plen <= dst.prefixlen:
                    tree = half["cells"].get(
                        _prefix_key(int(dst.network_address),
                                    dst.version, plen))
                    if tree is not None:
                        self._collect(streams, tree, port)

        self._collect(streams, self.both_any_tree, port)
        if not streams:
            return ()
        if len(streams) == 1:
            return streams[0]
        return _merge_streams(streams)

    def diagnose(self):
        """找出被前面规则整个包住的冗余项与动作相反的不可达项。

        每条被盖住的规则只挂到最早盖住它的规则(决定其命运的就是这一
        条),双方行号都带上;结果按被盖规则的匹配顺序排列。
        """
        redundant = []
        unreachable = []
        for priority, seq, rule in self.entries:
            coverer = None
            for cover_priority, cover_seq, candidate \
                    in self._coverer_candidates(rule):
                if (cover_priority, cover_seq) >= (priority, seq):
                    break
                if _covers(candidate, rule):
                    coverer = candidate
                    break
            if coverer is None:
                continue
            finding = ShadowFinding(
                "redundant" if coverer.action == rule.action
                else "unreachable", coverer, rule)
            if coverer.action == rule.action:
                redundant.append(finding)
            else:
                unreachable.append(finding)
        return Diagnosis(redundant, unreachable)



class RuleSet:
    """一组规则,按 priority 升序、同 priority 按加入先后参与匹配。

    match 先命中先算,全部落空才走默认策略。增删与 reload 后索引整体
    重建并原子替换:任何时刻 match 看到的都是一份完整规则集。
    """

    def __init__(self, lines=None, default_action=DEFAULT_ACTION):
        if default_action not in ACTIONS:
            raise ValueError("default_action must be one of {!r}".format(ACTIONS))
        self._lock = threading.RLock()
        self._stats = MatchStats()
        self._default_action = default_action
        self._entries = []          # (priority, seq, rule),seq 为加入序号
        self._next_seq = 0
        self._engine = _Engine([], default_action)
        self._diagnosis = None
        if lines is not None:
            self.reload(lines)

    # ---- 规则集视图 ----

    def rules(self):
        """当前规则列表的副本,顺序即匹配顺序(prio 升序、加入先后)。"""
        with self._lock:
            return [entry[2] for entry in self._engine.entries]

    def line_numbers(self):
        """当前规则在文本里对应的行号,按匹配顺序。"""
        with self._lock:
            return [entry[2].line_no for entry in self._engine.entries]

    def stats(self):
        """匹配统计,口径见 fwkit.stats。"""
        return self._stats

    def default_action(self, action=None):
        """读取默认策略;给了 action 就整体切换,随后立即生效。"""
        with self._lock:
            if action is None:
                return self._default_action
            if action not in ACTIONS:
                raise ValueError("default_action must be one of {!r}".format(ACTIONS))
            self._default_action = action
            self._engine = _Engine(self._entries, action)
            return action

    def diagnose(self):
        """冗余与不可达规则清单,结果带双方行号;规则变化后自动重算。"""
        with self._lock:
            if self._diagnosis is None:
                self._diagnosis = self._engine.diagnose()
            # 返回副本,避免调用方改动内部状态。
            return Diagnosis(self._diagnosis.redundant,
                             self._diagnosis.unreachable)

    def __len__(self):
        with self._lock:
            return len(self._entries)

    # ---- 加载与热更新 ----

    def _install_rule(self, rule):
        """观察单条规则装入的钩子。

        reload 在离线构建的新视图上逐条调用它;子类覆写可观察装载过程,
        抛异常会让整个 reload 失败、线上视图保持不动。
        """

    def _rebuild(self):
        """用当前 _entries 离线建好引擎后原子切换。"""
        engine = _Engine(self._entries, self._default_action)
        self._engine = engine
        self._diagnosis = None

    def add_rule(self, rule):
        """加一条规则,按 prio 插入匹配顺序,立即生效。"""
        with self._lock:
            self._entries.append((rule.priority, self._next_seq, rule))
            self._next_seq += 1
            self._rebuild()
            return rule

    def remove_rule(self, line_no):
        """按行号删掉匹配顺序里第一条对得上的规则;删到了返回 True。"""
        with self._lock:
            for index, (_priority, _seq, rule) in enumerate(self._entries):
                if rule.line_no == line_no:
                    del self._entries[index]
                    self._rebuild()
                    return True
            return False

    def reload(self, lines):
        """整体重载:先全部解析、在离线视图上装完,再一次性切换。

        lines 是规则文本或行的列表。解析或安装钩子抛异常时整体失败:
        线上规则集原封不动,绝不会出现半装或空窗放行。成功才记一次
        reload 统计。
        """
        if isinstance(lines, str):
            lines = lines.splitlines()
        with self._lock:
            parsed = parse_rules(lines)
            entries = []
            next_seq = self._next_seq
            for rule in parsed:
                self._install_rule(rule)
                entries.append((rule.priority, next_seq, rule))
                next_seq += 1
            engine = _Engine(entries, self._default_action)
            self._entries = entries
            self._next_seq = next_seq
            self._engine = engine
            self._diagnosis = None
            self._stats.reloads += 1
            return self

    # ---- 匹配 ----

    def match(self, packet):
        """给一个包判动作:prio 升序、同 prio 加入先后,先命中先算。"""
        with self._lock:
            return self._engine.match(packet, self._stats)
