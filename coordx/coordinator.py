"""coordx: 按顺序驱动一批参与者事务的协调者。

现状是单阶段的、严格按注册顺序串行推进：begin() 依次让每个参与者
开启本地事务，commit() 再依次让它们提交。参与者是注入进来的对象，
只能靠 begin()/commit() 沟通；一步抛错就原样往上抛，协调者不留任何
自己的状态，也不做补偿。

时间来源同样可注入（clock），默认取 time.monotonic，测试里可以换成
假时钟。协调者只在 begin() 时读一次时钟，用来算事务已经跑了多久。
"""

import time


class Participant:
    """参与者基类，代表一个能开启/提交本地事务的下游。

    注入对象可以继承它，也可以自己实现同名的 name/begin/commit。
    """

    def __init__(self, name):
        self.name = name

    def begin(self):
        """开启本地事务。"""
        raise NotImplementedError

    def commit(self):
        """提交本地事务。"""
        raise NotImplementedError


class Ledger(Participant):
    """内存账本参与者。

    begin() 之后的写入先暂存在 _pending 里，commit() 才真正落到 value 上。
    没有真实下游时用它演示、测试协调流程。
    """

    def __init__(self, name, value=0):
        super().__init__(name)
        self.value = value
        self._pending = None
        self._open = False

    def begin(self):
        self._open = True
        self._pending = None

    def commit(self):
        if not self._open:
            raise RuntimeError("%s: commit without begin" % self.name)
        if self._pending is not None:
            self.value = self._pending
        self._pending = None
        self._open = False

    def write(self, value):
        """登记一次改动，commit() 之后才对外可见。"""
        if not self._open:
            raise RuntimeError("%s: write outside transaction" % self.name)
        self._pending = value


class Coordinator:
    """按注册顺序串行驱动一批参与者。

    participants: 参与者序列，顺序即调用顺序。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic。
    """

    def __init__(self, participants, clock=time.monotonic):
        self._participants = list(participants)
        self._clock = clock
        self._active = False
        self._started_at = None

    def participants(self):
        """按注册顺序返回参与者名字组成的元组。"""
        return tuple(p.name for p in self._participants)

    def begin(self):
        """依次在各参与者上开启本地事务。"""
        if self._active:
            raise RuntimeError("coordinator already has an active transaction")
        for p in self._participants:
            p.begin()
        self._started_at = self._clock()
        self._active = True

    def commit(self):
        """依次提交各参与者，结束当前事务。"""
        if not self._active:
            raise RuntimeError("no active transaction to commit")
        for p in self._participants:
            p.commit()
        self._active = False
        self._started_at = None

    def active(self):
        """当前是否有进行中的事务。"""
        return self._active

    def elapsed(self):
        """当前事务已进行的秒数；没有活动事务时返回 0.0。"""
        if not self._active:
            return 0.0
        return self._clock() - self._started_at
