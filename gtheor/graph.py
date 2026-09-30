"""gtheor.graph: 公平组合游戏有向图局面的朴素实现（改造前基线）。

把一道公平组合游戏描述成一张有向图：结点是局面，边是一步合法走法。轮到谁走
谁就在当前结点挑一条出边走到后继结点，走到出度为空的结点即无路可走的一方输。
围绕这张图做几件最基础的事：

  - outcome        赢输：对给定起点递归枚举全部后继，只要有一个后继是必败就
                   判自己必胜，全部后继都必胜就判自己必败。对每个后继都重新
                   递归，已经算过的局面再次遇到也照重算，不记忆化，反复重入
                   同一局面，局面一多就指数级重复展开。
  - winning_move   一步制胜：从起点按后继给出的顺序逐个试走，返回第一个走到
                   必败后继的走法，没有则返回空。
  - min_moves      取胜最少步数：在对手尽力拖延的前提下取胜所需的最少步数
                   （按先手自己走的步数计）；必胜局面在必败后继里挑一条让
                   自己后续步数最少的走法，必败局面无解，返回空。
  - grundy         格林数：后继格林数集合的最小不出现非负整数，同样每个后继
                   重新递归。
  - xor_outcome    异或合并：把多个互相独立子游戏的起点格林数取异或，异或非
                   零则先手必胜，否则先手必败。
  - all_outcomes   全体局面：对图中每个结点逐个判赢输。

这些做法直观可靠，结果一眼能看穿；局面一多就指数级地重复展开。本文件是改造
前的基线，朴素路径在改造之后不得删除，新实现必须与它对同一批数据给出的事实
逐项对齐。

图上出现环时朴素递归无法终止，基线口径是碰到环直接判非法并抛 GraphErro，只
接受无环图；自环视同环。异常统一继承 GameErro 基类：GraphErro / StateErro。
"""


class GameErro(Exception):
    """公平组合游戏工具包所有异常的基类，非法输入一律快速失败。"""


class GraphErro(GameErro):
    """图非法：不是字典、结点或后继不是整数、后继落空、或含有环。"""


class StateErro(GameErro):
    """局面非法：不是整数，或不是图里的结点。"""


def _as_int(v, where):
    """把入参规整成 int，非法即抛 GraphErro。"""
    if isinstance(v, bool) or not isinstance(v, int):
        raise GraphErro("%s: 必须是整数，收到 %r" % (where, v))
    return int(v)


def _normalize_graph(graph):
    """把入参规整成 {结点: 后继元组}，非法即抛 GraphErro。

    要求每个后继都出现在图里（图是封闭的），出度为空的结点用空元组表示。
    """
    if not isinstance(graph, dict):
        raise GraphErro("图必须是结点到后继的字典，收到 %r" % (type(graph).__name__,))
    out = {}
    for k, v in graph.items():
        kk = _as_int(k, "局面")
        try:
            items = list(v)
        except TypeError:
            raise GraphErro("局面 %r 的后继必须可迭代，收到 %r" % (kk, v))
        out[kk] = tuple(_as_int(x, "后继") for x in items)
    for k, succ in out.items():
        for s in succ:
            if s not in out:
                raise GraphErro("局面 %r 的后继 %r 不在图里" % (k, s))
    return out


def _check_state(graph, state):
    """校验起点是图里的结点，非法即抛 StateErro。"""
    if isinstance(state, bool) or not isinstance(state, int):
        raise StateErro("局面必须是整数，收到 %r" % (state,))
    if state not in graph:
        raise StateErro("局面 %r 不是图里的结点" % (state,))


class GameKit:
    """公平组合游戏有向图局面的朴素工具集（改造前基线）。

    每次调用都把上一次的展开次数归零后重新累加，实例本身不保存任何跨调用的
    派生状态；同一批输入连续调用两次，结果与计数都应逐位一致。
    """

    def __init__(self):
        # 本次调用朴素递归实际重入局面的次数，进入调用前归零后重新累加。
        self.expansions = 0

    # ----------------------------------------------------------------
    # 赢输：对每个后继重新递归，反复重入同一局面
    # ----------------------------------------------------------------
    def outcome(self, graph, start):
        """起点局面的赢输，返回 win 或 loss。

        必胜（win）指轮到走的一方存在必胜策略；必败（loss）指无路可走或无论
        怎么走都把必胜局留给对手。出度为空的局面必败。非法输入抛 GraphErro，
        起点不是结点抛 StateErro，图中有环抛 GraphErro。
        """
        g = _normalize_graph(graph)
        _check_state(g, start)
        self.expansions = 0
        return self._rec_outcome(g, start, set())

    def _rec_outcome(self, g, state, path):
        """朴素递归：不记忆化，每个后继都从头再算一遍。"""
        self.expansions += 1
        if state in path:
            raise GraphErro("图中有环，朴素递归无法终止，结点 %r" % (state,))
        succ = g[state]
        if not succ:
            return "loss"
        path.add(state)
        try:
            for s in succ:
                if self._rec_outcome(g, s, path) == "loss":
                    return "win"
            return "loss"
        finally:
            path.discard(state)

    # ----------------------------------------------------------------
    # 一步制胜：按后继顺序逐个试走
    # ----------------------------------------------------------------
    def winning_move(self, graph, state):
        """返回一步走到必败后继的走法（后继结点），没有则返回 None。

        按后继给出的顺序逐个判定，返回第一个能制胜的后继。非法输入抛
        GraphErro，起点不是结点抛 StateErro，图中有环抛 GraphErro。
        """
        g = _normalize_graph(graph)
        _check_state(g, state)
        self.expansions = 0
        for s in g[state]:
            if self._rec_outcome(g, s, set()) == "loss":
                return s
        return None

    # ----------------------------------------------------------------
    # 取胜最少步数：在对手尽力拖延的前提下逼对方无路可走
    # ----------------------------------------------------------------
    def min_moves(self, graph, start):
        """先手必胜时把对方逼到无路可走所需的落子步数，必败局面返回 None。

        步数从起点算起，按双方各自走的步数计，先手因取胜而落子数为奇数；对手
        每一步都尽力拖延。必胜局面在每个必败后继里挑一条让自己后续步数最少的
        走法；必败局面无解，返回 None。终点无路可走的一方输，走到终点即取胜。
        非法输入抛 GraphErro，起点不是结点抛 StateErro，图中有环抛 GraphErro。
        """
        g = _normalize_graph(graph)
        _check_state(g, start)
        self.expansions = 0
        if self._rec_outcome(g, start, set()) == "loss":
            return None
        return self._rec_min(g, start, set())

    def _rec_min(self, g, state, path):
        """朴素递归求局面到终局的步数：必胜取最短，必败尽力拖延。"""
        self.expansions += 1
        if state in path:
            raise GraphErro("图中有环，朴素递归无法终止，结点 %r" % (state,))
        succ = g[state]
        if not succ:
            return 0
        path.add(state)
        try:
            if self._rec_outcome(g, state, set()) == "win":
                best = None
                for s in succ:
                    if self._rec_outcome(g, s, set()) == "loss":
                        cur = self._rec_min(g, s, path) + 1
                        if best is None or cur < best:
                            best = cur
                return best
            worst = None
            for s in succ:
                cur = self._rec_min(g, s, path) + 1
                if worst is None or cur > worst:
                    worst = cur
            return worst
        finally:
            path.discard(state)

    # ----------------------------------------------------------------
    # 格林数：后继格林数集合的最小不出现整数
    # ----------------------------------------------------------------
    def grundy(self, graph, start):
        """起点局面的格林数，同样的后继也逐个重新递归。

        出度为空的局面格林数为零。非法输入抛 GraphErro，起点不是结点抛
        StateErro，图中有环抛 GraphErro。
        """
        g = _normalize_graph(graph)
        _check_state(g, start)
        self.expansions = 0
        return self._rec_grundy(g, start, set())

    def _rec_grundy(self, g, state, path):
        """朴素递归求格林数，不记忆化。"""
        self.expansions += 1
        if state in path:
            raise GraphErro("图中有环，朴素递归无法终止，结点 %r" % (state,))
        succ = g[state]
        if not succ:
            return 0
        path.add(state)
        try:
            seen = set()
            for s in succ:
                seen.add(self._rec_grundy(g, s, path))
        finally:
            path.discard(state)
        mex = 0
        while mex in seen:
            mex += 1
        return mex

    # ----------------------------------------------------------------
    # 异或合并：多个独立子游戏起点格林数取异或
    # ----------------------------------------------------------------
    def xor_outcome(self, games):
        """多个独立子游戏异或合并后的胜负，返回 win 或 loss。

        games 是（图, 起点）的序列，每个子游戏互相独立；把各子游戏起点的格林
        数取异或，非零则先手必胜返回 win，否则返回 loss。games 为空时异或为
        零，返回 loss。非法输入抛 GraphErro，起点不是结点抛 StateErro。
        """
        self.expansions = 0
        total = 0
        for graph, start in games:
            g = _normalize_graph(graph)
            _check_state(g, start)
            total ^= self._rec_grundy(g, start, set())
        return "win" if total != 0 else "loss"

    # ----------------------------------------------------------------
    # 全体局面：逐个结点判赢输
    # ----------------------------------------------------------------
    def all_outcomes(self, graph):
        """对图中每个结点逐个判赢输，返回 {结点: win 或 loss}。

        每个结点都独立从头递归，结点之间不共享任何结果。非法输入抛
        GraphErro，图中有环抛 GraphErro。
        """
        g = _normalize_graph(graph)
        self.expansions = 0
        return {k: self._rec_outcome(g, k, set()) for k in g}

    # ----------------------------------------------------------------
    # 造一张减法游戏图，供异或合并使用
    # ----------------------------------------------------------------
    @staticmethod
    def heap_game(size, max_take):
        """造一张取石子减法游戏的图：结点是剩余石子数。

        从剩余 n 颗可一次取走一至 max_take 颗，后继是 n 减一至 n 减 max_take
        且不低于零的全部取值。size 为最大石子数，非负整数；max_take 为单次
        最多取走数，正整数。非法参数抛 GraphErro。
        """
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise GraphErro("石子数必须是非负整数，收到 %r" % (size,))
        if isinstance(max_take, bool) or not isinstance(max_take, int) or max_take < 1:
            raise GraphErro("单次最多取走数必须是正整数，收到 %r" % (max_take,))
        graph = {}
        for n in range(size + 1):
            succ = []
            for take in range(1, max_take + 1):
                if n - take >= 0:
                    succ.append(n - take)
            graph[n] = tuple(succ)
        return graph
