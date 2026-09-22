"""组织树配额。

QuotaTree 把总额度挂在根上，下级团队的份额从上级闲置里划出来。团队申请
先用自己的闲置份额，不够就沿祖先链向上借闲置额度（就近先借），归还时先
还借来的部分，再退自己的份额。每个节点只维护自身占用、借出、借入与下级
份额合计这几个滚动计数，申请、归还、查可用都只走祖先链，不扫子树。

每个节点守住一条不变量：自用 + 下级份额之和 + 借出 <= 自身份额。
"""

from .errors import UnknownTeam
from .ledger import Ledger
from .manager import check_amount


def _check_limit_amount(amount, what):
    """份额允许缩到 0，其余规则与 check_amount 一致。"""
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise ValueError("%s必须是非负整数，收到 %r" % (what, amount))
    return amount


class _Node:
    __slots__ = (
        "name", "parent", "limit", "own_used", "lent", "borrowed",
        "child_reserved", "children", "loans",
    )

    def __init__(self, name, parent, limit):
        self.name = name
        self.parent = parent          # 父节点，根为 None
        self.limit = limit            # 从上级闲置里划来的份额
        self.own_used = 0             # 自用占用（不含借来的部分）
        self.lent = 0                 # 借给下级的闲置额度
        self.borrowed = 0             # 从上级借来的占用总量
        self.child_reserved = 0       # 下级份额之和
        self.children = []
        self.loans = {}               # 借入明细：祖先名 -> 数量


class QuotaTree:
    """挂在组织树上的层级配额。"""

    def __init__(self, total, name="root", ledger=None):
        """以 total 为总额度建根，根默认叫 "root"。"""
        check_amount(total, "总额度")
        if not isinstance(name, str) or not name:
            raise ValueError("团队名必须是非空字符串，收到 %r" % (name,))
        self.ledger = ledger if ledger is not None else Ledger()
        root = _Node(name, None, total)
        self._root = root
        self._nodes = {name: root}
        self._requests = {}

    # ---- 结构 ----
    def add_node(self, name, parent, limit):
        """挂一个团队，份额从父团队闲置里划，闲置不够报 ValueError。"""
        if not isinstance(name, str) or not name:
            raise ValueError("团队名必须是非空字符串，收到 %r" % (name,))
        check_amount(limit, "份额")
        if name in self._nodes:
            raise ValueError("团队 %r 已经挂过了" % (name,))
        node_parent = self._nodes.get(parent)
        if node_parent is None:
            raise UnknownTeam("团队 %r 没挂过" % (parent,))
        if limit > self._idle(node_parent):
            raise ValueError(
                "团队 %r 只剩 %d 闲置，划不出 %d"
                % (parent, self._idle(node_parent), limit))
        node = _Node(name, node_parent, limit)
        node_parent.children.append(node)
        node_parent.child_reserved += limit
        self._nodes[name] = node

    def shrink(self, name, new_limit):
        """把团队份额缩到 new_limit，收走的额度沿祖先链一起减掉。

        收走的份额整棵子树都够不着（祖先的闲置不因此变多），占用压不住的
        部分缩不动就停住。返回缩容后被压到没余量（可用额为 0、新申请会被
        拒）的团队名，升序。new_limit 不小于当前份额时不缩，返回空列表。
        """
        node = self._require(name)
        _check_limit_amount(new_limit, "新份额")
        charge = node.own_used + node.child_reserved + node.lent
        target = max(new_limit, charge)
        if target >= node.limit:
            return []
        delta = node.limit - target
        node.limit = target
        ancestor = node.parent
        while ancestor is not None:
            ancestor.limit -= delta
            ancestor.child_reserved -= delta
            ancestor = ancestor.parent
        # 可用额沿祖先链累加，子节点的可用额 = 父节点可用额 + 自身闲置，
        # 可用额大于 0 的分支整棵剪掉，剩下的就是没余量的团队。
        above = 0
        ancestor = node.parent
        while ancestor is not None:
            above += self._idle(ancestor)
            ancestor = ancestor.parent
        squeezed = []
        stack = [(node, above + self._idle(node))]
        while stack:
            current, available = stack.pop()
            if available > 0:
                continue
            squeezed.append(current.name)
            for child in current.children:
                stack.append((child, self._idle(child)))
        return sorted(squeezed)

    # ---- 写 ----
    def acquire(self, name, amount, req_id=None):
        """申请额度。自有闲置不够就沿祖先链就近借，借不到返回 False。"""
        node = self._require(name)
        check_amount(amount, "申请量")
        done = self._replay(req_id, "acquire", name, amount)
        if done is not None:
            return done
        take = min(amount, self._idle(node))
        deficit = amount - take
        plan = []
        if deficit:
            need = deficit
            ancestor = node.parent
            while ancestor is not None and need > 0:
                idle = self._idle(ancestor)
                if idle > 0:
                    part = min(idle, need)
                    plan.append((ancestor, part))
                    need -= part
                ancestor = ancestor.parent
            if need > 0:
                self.ledger.record(name, "acquire", amount, False, req_id)
                self._remember(req_id, "acquire", name, amount, False)
                return False
        node.own_used += take
        for ancestor, part in plan:
            ancestor.lent += part
            node.loans[ancestor.name] = node.loans.get(ancestor.name, 0) + part
        node.borrowed += deficit
        self.ledger.record(name, "acquire", amount, True, req_id)
        self._remember(req_id, "acquire", name, amount, True)
        return True

    def release(self, name, amount, req_id=None):
        """归还额度，先还借来的部分。归还量超过当前占用报 ValueError。"""
        node = self._require(name)
        check_amount(amount, "归还量")
        done = self._replay(req_id, "release", name, amount)
        if done is not None:
            return done
        if amount > node.own_used + node.borrowed:
            raise ValueError(
                "团队 %r 只占着 %d，退不了 %d"
                % (name, node.own_used + node.borrowed, amount))
        repay = min(amount, node.borrowed)
        if repay:
            left = repay
            ancestor = node.parent
            while ancestor is not None and left > 0:
                loan = node.loans.get(ancestor.name)
                if loan:
                    pay = min(loan, left)
                    if pay == loan:
                        del node.loans[ancestor.name]
                    else:
                        node.loans[ancestor.name] = loan - pay
                    ancestor.lent -= pay
                    left -= pay
                ancestor = ancestor.parent
            node.borrowed -= repay
        node.own_used -= amount - repay
        self.ledger.record(name, "release", amount, True, req_id)
        self._remember(req_id, "release", name, amount, True)
        return True

    # ---- 读 ----
    def available(self, name):
        """还能申请的额度：自身闲置加上各级祖先的闲置。"""
        node = self._require(name)
        total = 0
        while node is not None:
            total += self._idle(node)
            node = node.parent
        return total

    def used(self, name):
        """当前占用，含从上级借来的部分。"""
        node = self._require(name)
        return node.own_used + node.borrowed

    def borrowed(self, name):
        """当前占用里从上级借来的部分。"""
        return self._require(name).borrowed

    def idle(self, name):
        """自身闲置：份额减去自用、下级份额与借出。"""
        return self._idle(self._require(name))

    def limit(self, name):
        """当前份额。"""
        return self._require(name).limit

    def teams(self):
        """全部团队名，升序。"""
        return sorted(self._nodes)

    def children(self, name):
        """直接下级团队名，升序。"""
        return sorted(child.name for child in self._require(name).children)

    def parent(self, name):
        """上级团队名，根返回 None。"""
        node = self._require(name)
        return node.parent.name if node.parent is not None else None

    @property
    def root(self):
        """根团队名。"""
        return self._root.name

    # ---- 内部 ----
    @staticmethod
    def _idle(node):
        return node.limit - node.own_used - node.child_reserved - node.lent

    def _require(self, name):
        node = self._nodes.get(name)
        if node is None:
            raise UnknownTeam("团队 %r 没挂过" % (name,))
        return node

    def _replay(self, req_id, kind, name, amount):
        if req_id is None:
            return None
        seen = self._requests.get(req_id)
        if seen is None:
            return None
        if seen[:3] != (kind, name, amount):
            raise ValueError(
                "请求 ID %r 已经用在 %r 上，不能改口" % (req_id, seen[:3]))
        self.ledger.record(name, "replay", amount, seen[3], req_id)
        return seen[3]

    def _remember(self, req_id, kind, name, amount, result):
        if req_id is not None:
            self._requests[req_id] = (kind, name, amount, result)
