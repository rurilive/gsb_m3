"""orderbook 现状演示。

第一段：搭一撮订单，用朴素订单列表下单、看挂单顺序与某一侧的挂单；
第二段：预留的撮合、部分成交与盘口演示位子（见文末注释）。
"""

from orderbook.engine import Engine


def main():
    print("=== 朴素订单列表 ===")
    e = Engine()
    e.place("alice", "buy", 100, 5)
    e.place("bob", "sell", 101, 3)
    e.place("carol", "buy", 99, 2)
    print("  挂单 %s" % ([o.order_id for o in e.open_orders()],))
    print("  买盘 %s" % ([(o.order_id, o.price, o.qty) for o in e.depth("buy")],))
    print("  卖盘 %s" % ([(o.order_id, o.price, o.qty) for o in e.depth("sell")],))
    print("  成交流水 %s" % (e.trades(),))
    print("  挂单数 -> %d" % len(e))
    e.cancel(1)
    print("  撤掉 1 之后挂单 %s" % ([o.order_id for o in e.open_orders()],))

    # TODO(撮合与盘口): 在 orderbook 里补出价格优先加时间优先的订单簿、
    # 新单与对手盘逐档撮合、部分成交留残量与撤销残量、市价单口径、
    # 买卖前 N 档盘口聚合、无交叉与量守恒不变量之后，在这里加一段演示：
    # 先挂几笔不同价位的买卖单建出盘口，打印买一卖一与前几档盘口；再下
    # 一笔能把对手盘吃穿的订单，打印产生的成交流水（各笔的价、量、被动方）、
    # 剩余残量，并确认买盘价格不高于卖盘价格、下单量等于成交量加残量；
    # 接着下市价单看它逐档吃单，再撤掉一笔没成交完的残量确认它从簿上消失。


if __name__ == "__main__":
    main()
