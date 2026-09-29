"""状态机内核：状态集合、转移表与推进入口。

当前能力只覆盖一层机器：注册若干状态与转移，用 step 沿转移推进，并把
历史推进路径记在 trail 里。守卫与动作、子状态机嵌套、历史态与冲突检测
都留待在这个基础上补齐。

转移用一个 (source, target) 二元组标识，任何一个状态都不带事件名之外的
维度，step 也只认目标状态。
"""

from .errors import DefinitionError, InvalidTransition


class Machine:
    """一层状态机。

    initial 是初始状态名，states 与 transitions 都是可迭代的名字集合，
    transitions 里的每一项是 (source, target) 二元组。
    """

    def __init__(self, initial, states=(), transitions=()):
        self._initial = initial
        self._states = set()
        self._edges = {}  # source -> set(target)
        self._trail = []
        for name in states:
            self.add_state(name)
        for source, target in transitions:
            self.add_transition(source, target)
        if initial not in self._states:
            raise DefinitionError("初始状态未注册: %r" % (initial,))
        self._current = initial
        self._trail.append(initial)

    def add_state(self, name):
        """注册一个状态，重复注册在定义期 fail-fast。"""
        if not isinstance(name, str) or not name:
            raise DefinitionError("状态名必须是非空字符串: %r" % (name,))
        if name in self._states:
            raise DefinitionError("状态重复注册: %r" % (name,))
        self._states.add(name)
        self._edges[name] = set()
        return self

    def add_transition(self, source, target):
        """注册一条从 source 到 target 的转移。

        两端都必须是已注册状态，否则在定义期抛 DefinitionError。
        """
        for name in (source, target):
            if name not in self._states:
                raise DefinitionError("转移指向未注册状态: %r" % (name,))
        self._edges[source].add(target)
        return self

    @property
    def current(self):
        """当前状态名。"""
        return self._current

    @property
    def states(self):
        """已注册状态的有序元组，按注册先后返回。"""
        return tuple(sorted(self._states))

    @property
    def trail(self):
        """从初始状态到当前状态的推进路径，含首尾。"""
        return list(self._trail)

    @property
    def initial(self):
        """初始状态名。"""
        return self._initial

    def targets(self, source=None):
        """从 source 出发的全部目标状态；source 缺省为当前状态。"""
        if source is None:
            source = self._current
        if source not in self._states:
            raise DefinitionError("未知状态: %r" % (source,))
        return tuple(sorted(self._edges[source]))

    def can(self, target):
        """当前状态能否一步推进到 target。"""
        if target not in self._states:
            raise DefinitionError("未知状态: %r" % (target,))
        return target in self._edges[self._current]

    def reset(self):
        """回到初始状态并清空历史路径。"""
        self._current = self._initial
        self._trail = [self._initial]
        return self._current

    def step(self, target):
        """沿转移推进到 target，返回推进后的当前状态。

        非法转移 fail-fast 抛 InvalidTransition，当前状态与路径都不受影响。
        """
        if target not in self._states:
            raise InvalidTransition("目标状态未注册: %r" % (target,))
        if target not in self._edges[self._current]:
            raise InvalidTransition(
                "当前状态 %r 上没有通往 %r 的转移" % (self._current, target))
        self._current = target
        self._trail.append(target)
        return self._current

    def __repr__(self):
        return "<Machine current=%r states=%d>" % (self._current, len(self._states))