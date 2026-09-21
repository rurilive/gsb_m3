"""规则、数据包的表示,以及规则文本的解析。

规则文本一行一条:

    [prio=<int>] <action> <src> <dst> <ports>

action 取 allow 或 deny;src 和 dst 是 CIDR 或 any;ports 是 any、单个
端口或 lo-hi 区间。空行和以 # 开头的行会被跳过。
"""

import ipaddress

ANY = "any"
ACTION_ALLOW = "allow"
ACTION_DENY = "deny"
ACTIONS = (ACTION_ALLOW, ACTION_DENY)

PORT_MIN = 0
PORT_MAX = 65535

# 没写 prio 的规则取这个值。
DEFAULT_PRIORITY = 100


class RuleSyntaxError(ValueError):
    """规则文本不合法。line_no 指向出错的那一行。"""

    def __init__(self, line_no, message):
        super().__init__("line {}: {}".format(line_no, message))
        self.line_no = line_no
        self.message = message


def _as_network(value, line_no):
    """把 None、字符串或网段对象统一成 ipaddress 网段对象或 None。"""
    if value is None:
        return None
    if isinstance(value, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
        return value
    try:
        # strict=False: 10.1.2.3/8 这类带主机位的写法按掩码归一。
        return ipaddress.ip_network(value, strict=False)
    except ValueError as exc:
        raise RuleSyntaxError(line_no, "bad address {!r}: {}".format(value, exc)) from None


def _parse_ports(text, line_no):
    """解析 any、单端口或 lo-hi 区间,返回闭区间。"""
    if text == ANY:
        return PORT_MIN, PORT_MAX
    if "-" in text:
        lo_text, _, hi_text = text.partition("-")
    else:
        lo_text = hi_text = text
    try:
        lo = int(lo_text)
        hi = int(hi_text)
    except ValueError:
        raise RuleSyntaxError(line_no, "bad port {!r}".format(text)) from None
    if not PORT_MIN <= lo <= hi <= PORT_MAX:
        raise RuleSyntaxError(line_no, "port range reversed or out of range: {!r}".format(text))
    return lo, hi


class Packet:
    """待匹配的数据包。src 和 dst 收 IP 字符串,port 是整数端口。"""

    __slots__ = ("src", "dst", "port")

    def __init__(self, src, dst, port):
        self.src = ipaddress.ip_address(src)
        self.dst = ipaddress.ip_address(dst)
        self.port = int(port)

    @property
    def family(self):
        """地址族,4 或 6。"""
        return self.src.version

    def __eq__(self, other):
        if not isinstance(other, Packet):
            return NotImplemented
        return (self.src, self.dst, self.port) == (other.src, other.dst, other.port)

    def __hash__(self):
        return hash((self.src, self.dst, self.port))

    def __repr__(self):
        return "Packet({} -> {}:{})".format(self.src, self.dst, self.port)


class Rule:
    """一条规则。

    src 和 dst 是 None(any)或 ipaddress 网段对象,port_lo 和 port_hi 是
    含端点的端口下上限。priority 数字小的排前面。line_no 是规则落在文本
    里的行号,程序里直接构造的规则可以是 0。
    """

    __slots__ = ("line_no", "priority", "action", "src", "dst", "port_lo", "port_hi")

    def __init__(self, action, src=None, dst=None, port_lo=PORT_MIN, port_hi=PORT_MAX,
                 priority=DEFAULT_PRIORITY, line_no=0):
        if action not in ACTIONS:
            raise RuleSyntaxError(line_no, "bad action {!r}".format(action))
        self.action = action
        self.src = _as_network(src, line_no)
        self.dst = _as_network(dst, line_no)
        self.port_lo = int(port_lo)
        self.port_hi = int(port_hi)
        if self.port_lo > self.port_hi:
            raise RuleSyntaxError(line_no, "port range reversed")
        self.priority = int(priority)
        self.line_no = int(line_no)

    @classmethod
    def parse(cls, text, line_no=0):
        """解析一行规则文本。"""
        tokens = text.split()
        priority = DEFAULT_PRIORITY
        if tokens and tokens[0].lower().startswith("prio="):
            raw = tokens.pop(0)[len("prio="):]
            try:
                priority = int(raw)
            except ValueError:
                raise RuleSyntaxError(line_no, "bad priority {!r}".format(raw)) from None
        if len(tokens) != 4:
            raise RuleSyntaxError(line_no, "expected [prio=N] action src dst ports, got {!r}".format(text))
        action, src_text, dst_text, ports_text = tokens
        if action not in ACTIONS:
            raise RuleSyntaxError(line_no, "bad action {!r}".format(action))
        src = _as_network(None if src_text == ANY else src_text, line_no)
        dst = _as_network(None if dst_text == ANY else dst_text, line_no)
        port_lo, port_hi = _parse_ports(ports_text, line_no)
        return cls(action, src=src, dst=dst, port_lo=port_lo, port_hi=port_hi,
                   priority=priority, line_no=line_no)

    def matches(self, packet):
        """这个包是否落在这条规则的选择器里。地址族不同一律不算命中。"""
        if self.src is not None:
            if packet.src.version != self.src.version or packet.src not in self.src:
                return False
        if self.dst is not None:
            if packet.dst.version != self.dst.version or packet.dst not in self.dst:
                return False
        return self.port_lo <= packet.port <= self.port_hi

    def selector(self):
        """规范化之后的选择器,可以直接拿来比两条规则是不是同一组条件。"""
        return (self.src, self.dst, self.port_lo, self.port_hi)

    def __repr__(self):
        return "Rule(line={}, prio={}, {} {} -> {} ports {}-{})".format(
            self.line_no, self.priority, self.action,
            self.src if self.src is not None else ANY,
            self.dst if self.dst is not None else ANY,
            self.port_lo, self.port_hi)


def parse_rules(lines, first_line_no=1):
    """逐行解析规则文本,跳过空行和 # 注释,返回 Rule 列表。

    lines 可以是整段文本,也可以是行的列表。行号从 first_line_no 起算。
    """
    if isinstance(lines, str):
        lines = lines.splitlines()
    rules = []
    for offset, raw in enumerate(lines):
        line_no = first_line_no + offset
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        rules.append(Rule.parse(text, line_no))
    return rules
