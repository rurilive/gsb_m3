"""orderbook 的朴素订单列表现状实现（改造前的起点）。

现在还没有订单簿：不维护买一卖一档位，不做价格优先与时间优先的排序，
新订单不会和对手盘撮合，也不会产生任何成交。Order 只是一条记下
订单号、账户、方向、价格与数量的普通记录；Engine 只把订单堆进一张
按到达顺序排列的列表里，place 返回一个订单号，cancel 把对应订单从
列表中删掉。没有市价单、没有部分成交、没有盘口、没有无交叉与量守恒
的不变量。订单簿、撮合、部分成交与盘口见任务描述。
"""


class Order:
    """一条普通订单记录，字段固定，不做任何撮合。"""

    def __init__(self, order_id, account, side, price, qty):
        self.order_id = order_id
        self.account = account
        self.side = side
        self.price = price
        self.qty = qty


class Engine:
    """只按到达顺序存放订单的朴素订单列表。"""

    def __init__(self):
        self._orders = []
        self._next_id = 1

    def place(self, account, side, price, qty):
        """下单，把一条订单追加到列表里并返回订单号。

        只做最基础的校验：账户非空、方向只能是 buy 或 sell、价格是正的
        int、数量是正的 int，不合法就抛 ValueError。这里不做价格优先与
        时间优先的排序，也不和对手盘撮合。
        """
        if not isinstance(account, str) or account == "":
            raise ValueError("account must be a non-empty str")
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
            raise ValueError("price must be a positive int")
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            raise ValueError("qty must be a positive int")
        oid = self._next_id
        self._next_id += 1
        self._orders.append(Order(oid, account, side, price, qty))
        return oid

    def cancel(self, order_id):
        """撤单，把对应订单从列表里删掉，订单不存在就报 KeyError。"""
        for i, o in enumerate(self._orders):
            if o.order_id == order_id:
                del self._orders[i]
                return True
        raise KeyError(order_id)

    def open_orders(self):
        """按到达顺序返回还没撤的订单。"""
        return tuple(self._orders)

    def depth(self, side):
        """返回某一侧的所有挂单，按到达顺序，不做任何价格聚合。"""
        return tuple(o for o in self._orders if o.side == side)

    def trades(self):
        """成交流水，现状下永远为空，因为还不撮合。"""
        return ()

    def __len__(self):
        return len(self._orders)
