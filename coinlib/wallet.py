"""最朴素的钱包实现：余额就是一个浮点数。

加减就是浮点加减，没有货币概念，也不做任何精度处理。它够用于看一眼余额，
但撑不起需要精确到分、需要多币种、需要把一笔钱拆给多方的场景。
"""


class Wallet:
    """一个用浮点数存余额的钱包。"""

    def __init__(self, balance=0.0):
        """用一个初始余额构造钱包，缺省是 0.0。"""
        self._balance = float(balance)

    def balance(self):
        """返回当前余额，浮点数。"""
        return self._balance

    def deposit(self, amount):
        """加一笔钱，直接做浮点加法，返回新的余额。"""
        self._balance = self._balance + float(amount)
        return self._balance

    def withdraw(self, amount):
        """减一笔钱，直接做浮点减法，返回新的余额。"""
        self._balance = self._balance - float(amount)
        return self._balance

    def __repr__(self):
        return "Wallet(balance=%r)" % (self._balance,)
