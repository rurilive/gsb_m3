"""slopeopt 基线：斜率型动态规划最优化工具包（改造前朴素实现对）。

目前只有最直白的一条路子：状态转移形如 dp 取此前某个状态加上一个含下标的
代价，朴素做法对每个下标枚举全部更早的下标逐个算再取最小，两两枚举是平方
量级，规模一大就慢，但结果正确。

对外能力：
  - OptKit.optimize 求最小代价下的 dp 序列、最优决策下标序列与各步比较计数；
  - OptKit.compare 对一批输入逐项给出朴素结果，作为后续高效路径的对照事实。

口径要点（与基线测试一字对齐）：
  - 决策下标并列时取最小下标；
  - 结果只依赖固定输入与构造参数，不依赖模块级可变状态；
  - 计数字段在每次调用开始时归零重算，不把上一次的累加带进来；
  - 非法输入在进入求解前快速失败，异常统一继承 OptErro。
"""


class OptErro(Exception):
    """slopeopt 全部对外异常的根。"""


class SequenceErro(OptErro):
    """权值序列本身非法（空序列、元素不是整数、不足以构成转移）。"""


class ProgramErro(OptErro):
    """代价程序参数非法（斜率或截距不是整数、步长越界等）。"""


class Program:
    """线性代价程序：代价(j, k) = slope * j + intercept + k。

    参数需为整数（布尔不算整数），slope 可正可负可为零。
    """

    __slots__ = ("slope", "intercept", "k")

    def __init__(self, slope, intercept, k):
        if isinstance(slope, bool) or not isinstance(slope, int):
            raise ProgramErro("斜率必须是整数")
        if isinstance(intercept, bool) or not isinstance(intercept, int):
            raise ProgramErro("截距必须是整数")
        if isinstance(k, bool) or not isinstance(k, int):
            raise ProgramErro("步长必须是整数")
        if k < 1:
            raise ProgramErro("步长至少为一")
        self.slope = slope
        self.intercept = intercept
        self.k = k

    def cost(self, j, i):
        """把状态 j 转移到下标 i 的代价（朴素口径，逐项算一遍）。"""
        return self.slope * j + self.intercept + (i - j) * self.k


def _check_weights(weights):
    """权值序列校验：必须是长度至少为一的整数序列。"""
    if weights is None:
        raise SequenceErro("权值序列不能为空")
    if isinstance(weights, (bytes, bytearray)):
        raise SequenceErro("权值序列必须是整数序列")
    try:
        seq = list(weights)
    except TypeError:
        raise SequenceErro("权值序列必须是可迭代的整数序列")
    if len(seq) == 0:
        raise SequenceErro("权值序列不能为空")
    for v in seq:
        if isinstance(v, bool) or not isinstance(v, int):
            raise SequenceErro("权值序列的每个元素都必须是整数")
    return seq


class OptKit:
    """朴素求解器：对每个下标枚举全部更早下标，逐个算代价取最小。"""

    def __init__(self, program):
        if not isinstance(program, Program):
            raise ProgramErro("需要传入 Program 实例")
        self.program = program
        self.steps = 0          # 最近一次 optimize 的比较次数
        self.transitions = 0    # 最近一次 optimize 的候选转移总数

    def optimize(self, weights):
        """朴素求最优 dp 序列与决策下标序列。

        返回形如 {"dp": [...], "best": [...], "steps": 整数}。
        dp[0] 取第一个权值本身；下标 i（至少为一步长）取全部 j <= i - k 中
        dp[j] + 代价(j, i) 的最小值，最小下标并列时取更小的 j。
        """
        seq = _check_weights(weights)
        n = len(seq)
        k = self.program.k
        self.steps = 0
        self.transitions = 0

        dp = [0] * n
        best = [-1] * n
        dp[0] = seq[0]
        best[0] = 0
        for i in range(1, n):
            chosen = None
            for j in range(0, i - k + 1):
                self.transitions += 1
                cand = dp[j] + self.program.cost(j, i)
                self.steps += 1
                if chosen is None or cand < chosen[0]:
                    chosen = (cand, j)
            if chosen is None:
                dp[i] = seq[i]
                best[i] = i
            else:
                dp[i] = chosen[0]
                best[i] = chosen[1]
        return {"dp": dp, "best": best, "steps": self.steps}

    def compare(self, weights):
        """对同一批权值走一遍朴素与（将来补上的）高效两路并逐项对照。

        当前只有朴素一路，故两路结果就是同一份事实，逐项一致。
        """
        seq = _check_weights(weights)
        baseline = self.optimize(seq)
        return {
            "weights": seq,
            "baseline": baseline,
            "fast": {"dp": list(baseline["dp"]), "best": list(baseline["best"])},
            "agree": True,
            "baseline_steps": baseline["steps"],
            "fast_steps": baseline["steps"],
        }
