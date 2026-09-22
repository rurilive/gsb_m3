"""组织树配额：上级额度兜住整棵子树，子团队不够就借上级闲置顶上。

模型
----
每个节点有一份基础份额 limit（add_node 时从父节点闲置里划出，shrink 可收回），
外加临时借来的 borrowed，合起来是当前能支配的总额度 effective = limit +
borrowed。节点自留闲置 free = effective - 自用 - 下级份额之和，恒不为负：
占用不超额度，下级之和加自用不超上级。

申请先吃自己的 free，不够就沿祖先链逐级借：缺口上报给父节点，父节点闲置够
就直接顶上，不够就自己再向上借，一路到根；根没有上级，根闲置不够就整笔拒掉，
不欠账。归还先还借的：释放出来的占用先冲抵 borrowed，借来的份额逐级还回
上级池子。

下级份额汇总 children_eff 挂在节点上就地维护，借还与缩容只沿祖先链走
O(深度)，不扫子树。available(name) 报的是当前能申请到的最大量：自留闲置加
沿祖先链可借的闲置之和。
"""

from .errors import UnknownTeam
from .ledger import Ledger
from .manager import check_amount


class _Node:
    __slots__ = ("name", "parent", "limit", "borrowed", "self_used",
                 "children_eff", "children")

    def __init__(self, name, parent, limit):
        self.name = name
        self.parent = parent
        self.limit = limit
        self.borrowed = 0
        self.self_used = 0
        self.children_eff = 0
        self.children = []

    def effective(self):
        return self.limit + self.borrowed

    def free(self):
        return self.effective() - self.self_used - self.children_eff


class QuotaTree:
    """挂在组织树上的层级配额。"""

    def __init__(self, total, ledger=None, root_name="root"):
        check_amount(total, "总额度")
        if not isinstance(root_name, str) or not root_name:
            raise ValueError("根节点名必须是非空字符串，收到 %r" % (root_name,))
        self.ledger = ledger if ledger is not None else Ledger()
        self.root = root_name
        self._nodes = {root_name: _Node(root_name, None, total)}
        self._requests = {}

    # ---- 建树 ----
    def add_node(self, name, parent, limit):
        """从父节点闲置里划出 limit 给新节点，划不出报 ValueError。"""
        if not isinstance(name, str) or not name:
            raise ValueError("节点名必须是非空字符串，收到 %r" % (name,))
        check_amount(limit, "份额")
        if name in self._nodes:
            raise ValueError("节点 %r 已经存在了" % (name,))
        p = self._require(parent)
        if limit > p.free():
            raise ValueError(
                "父节点 %r 只剩 %d 闲置，划不出 %d" % (parent, p.free(), limit))
        node = _Node(name, p, limit)
        p.children.append(node)
        p.children_eff += limit
        self._nodes[name] = node

    # ---- 写 ----
    def acquire(self, name, amount, req_id=None):
        """申请额度。自留闲置加祖先可借闲置够就扣下返回 True，不够返回 False。"""
        node = self._require(name)
        check_amount(amount, "申请量")
        done = self._replay(req_id, "acquire", name, amount)
        if done is not None:
            return done
        ok = amount <= self._available_node(node)
        if ok:
            node.self_used += amount
            self._borrow_up(node)
        self.ledger.record(name, "acquire", amount, ok, req_id)
        self._remember(req_id, "acquire", name, amount, ok)
        return ok

    def release(self, name, amount, req_id=None):
        """归还额度，先还借的。归还量超过当前占用报 ValueError。"""
        node = self._require(name)
        check_amount(amount, "归还量")
        done = self._replay(req_id, "release", name, amount)
        if done is not None:
            return done
        if amount > node.self_used:
            raise ValueError(
                "节点 %r 只占着 %d，退不了 %d" % (name, node.self_used, amount))
        node.self_used -= amount
        self._settle_up(node)
        self.ledger.record(name, "release", amount, True, req_id)
        self._remember(req_id, "release", name, amount, True)
        return True

    def shrink(self, name, new_limit):
        """把节点份额缩到 new_limit，只收闲置，缩不动就停在下限。

        下限 = 自用 + 下级份额 - 借入，低于下限的 new_limit 会被抬到下限。
        返回子树里被这次缩容压到没余量（可用额从正变零、新申请被拒）的团队，
        按名字升序。缩中间节点只是把闲置还进父池，子树整体可借总量不变；
        缩根等于砍总预算，才可能把团队压到零。
        """
        node = self._require(name)
        if isinstance(new_limit, bool) or not isinstance(new_limit, int) \
                or new_limit < 0:
            raise ValueError("新份额必须是非负整数，收到 %r" % (new_limit,))
        if new_limit >= node.limit:
            return []
        members = []
        stack = [node]
        while stack:
            x = stack.pop()
            members.append(x)
            stack.extend(x.children)
        before = dict((x.name, self._available_node(x)) for x in members)
        floor = node.self_used + node.children_eff - node.borrowed
        new = new_limit if new_limit > floor else floor
        delta = node.limit - new
        if delta > 0:
            node.limit = new
            if node.parent is not None:
                node.parent.children_eff -= delta
            self._settle_up(node)
        return sorted(x.name for x in members
                      if before[x.name] > 0 and self._available_node(x) == 0)

    # ---- 读 ----
    def available(self, name):
        """当前还能申请到的最大量：自留闲置加沿祖先链可借的闲置。"""
        return self._available_node(self._require(name))

    def used(self, name):
        """节点自己的当前占用（不含下级）。"""
        return self._require(name).self_used

    def limit(self, name):
        """节点的基础份额。"""
        return self._require(name).limit

    def borrowed(self, name):
        """节点当前从上级借来的份额。"""
        return self._require(name).borrowed

    def effective(self, name):
        """limit + borrowed，节点当前能支配的总额度。"""
        return self._require(name).effective()

    def free(self, name):
        """节点自留闲置：effective - 自用 - 下级份额之和。"""
        return self._require(name).free()

    def nodes(self):
        """全部节点名，升序。"""
        return sorted(self._nodes)

    def children(self, name):
        """直接下级节点名，升序。"""
        return sorted(x.name for x in self._require(name).children)

    def parent(self, name):
        """父节点名，根节点返回 None。"""
        node = self._require(name)
        return node.parent.name if node.parent is not None else None

    # ---- 内部 ----
    def _require(self, name):
        node = self._nodes.get(name)
        if node is None:
            raise UnknownTeam("节点 %r 不存在" % (name,))
        return node

    def _available_node(self, node):
        total = 0
        x = node
        while x is not None:
            total += x.free()
            x = x.parent
        return total

    def _borrow_up(self, node):
        """node 占用涨完后，把出现的缺口沿祖先链逐级借来补上。"""
        x = node
        while True:
            deficit = x.self_used + x.children_eff - x.limit - x.borrowed
            if deficit <= 0:
                return
            p = x.parent
            if p is None:
                raise RuntimeError("根节点额度被击穿，available 预检漏了")
            x.borrowed += deficit
            p.children_eff += deficit
            x = p

    def _settle_up(self, node):
        """归还或缩容后，沿祖先链把不再需要的借入份额逐级还回去。"""
        x = node
        while x is not None:
            target = x.self_used + x.children_eff - x.limit
            if target < 0:
                target = 0
            if x.borrowed > target:
                give = x.borrowed - target
                x.borrowed = target
                if x.parent is not None:
                    x.parent.children_eff -= give
            x = x.parent

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
