"""bitmaskx.bitmask: 集合上的状压工具（当前为改造前基线）。

本模块以元素总数 size 为底座，把所有子集表示成整数位掩码。
当前实现全部是朴素枚举：

  - 最短哈密顿路径与回路：对起点之外的全部点枚举全排列，逐个算代价取最小；
  - 集合覆盖：按个数从小到大枚举全部子集组合，逐个判定能否盖住目标集合；
  - 最优划分：递归枚举全部集合划分，逐个校验每组内部两两相容并取组数最小。

这些做法结果正确，可规模一大就指数甚至阶乘。另给三条独立的递归回溯做法，
用于与新路逐项对照。

全部只依赖标准库。
"""


class Erro(Exception):
    """本包所有异常的根，上层只认这一个。"""


class SizeErro(Erro):
    """元素规模或下标越界。"""


class GraphErro(Erro):
    """图的权矩阵或相容矩阵不合法。"""


class WeightErro(Erro):
    """权值不是数或形状不对。"""


class CoverErro(Erro):
    """覆盖目标集合的形态不合法，或不存在覆盖方案。"""


_INT_TYPES = (int,)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class MaskDp:
    """以位掩码为底座的集合状压工具（基线朴素版）。

    规模 size 指元素个数，元素下标为 0 到 size 减一。
    朴素路径与独立回溯路径各自的枚举次数按调用前归零重算。
    """

    def __init__(self, size):
        if not _is_int(size) or size < 0:
            raise SizeErro("size 必须是不小于零的整数")
        self._size = size
        self._reset_counts()

    # ---------------------------------------------------------------- 基本

    def _reset_counts(self):
        self.perm_visits = 0
        self.cover_visits = 0
        self.partition_visits = 0
        self.backtrack_visits = 0

    @property
    def size(self):
        return self._size

    def full_mask(self):
        """全体元素对应的掩码。"""
        return (1 << self._size) - 1

    def mask_of(self, indices):
        """把下标序列折成掩码，下标越界或重复一律报错。"""
        mask = 0
        seen = set()
        for i in indices:
            if not _is_int(i) or i < 0 or i >= self._size:
                raise SizeErro("下标越界：%r" % (i,))
            if i in seen:
                raise SizeErro("下标重复：%r" % (i,))
            seen.add(i)
            mask |= 1 << i
        return mask

    def elements_of(self, mask):
        """把掩码展开成升序下标列表，越界掩码报错。"""
        if not _is_int(mask) or mask < 0 or mask > self.full_mask():
            raise SizeErro("掩码越界：%r" % (mask,))
        out = []
        i = 0
        while mask:
            if mask & 1:
                out.append(i)
            mask >>= 1
            i += 1
        return out

    # ------------------------------------------------------------ 权矩阵校验

    def _check_square(self, matrix, label):
        if not isinstance(matrix, (list, tuple)) or len(matrix) != self._size:
            raise GraphErro("%s 必须是 %d 行" % (label, self._size))
        for row in matrix:
            if not isinstance(row, (list, tuple)) or len(row) != self._size:
                raise GraphErro("%s 每行必须是 %d 个元素" % (label, self._size))
            for value in row:
                if not _is_number(value):
                    raise WeightErro("%s 含非数值元素：%r" % (label, value))
        return matrix

    def _check_start(self, start):
        if not _is_int(start) or start < 0 or start >= self._size:
            raise GraphErro("起点越界：%r" % (start,))
        return start

    # ------------------------------------------- 最短哈密顿路径（全排列枚举）

    def shortest_hamiltonian(self, dist, start=0):
        """从 start 出发访问全部点一次的最短路径，返回（代价，路径）。

        并列时取路径字典序最小的一条。朴素做法枚举起点之外的全部排列。
        """
        self._reset_counts()
        if self._size == 0:
            raise GraphErro("没有点，无法求哈密顿路径")
        self._check_square(dist, "dist")
        self._check_start(start)
        rest = [i for i in range(self._size) if i != start]
        best_cost = None
        best_path = None
        for perm in self._permutations(rest):
            path = (start,) + perm
            cost = 0
            for k in range(len(path) - 1):
                cost += dist[path[k]][path[k + 1]]
            self.perm_visits += 1
            if best_cost is None or cost < best_cost or (cost == best_cost and path < best_path):
                best_cost = cost
                best_path = path
        return best_cost, list(best_path)

    def _permutations(self, items):
        """生成 items 的全部排列，朴素递归。"""
        if not items:
            yield ()
            return
        for idx in range(len(items)):
            head = items[idx]
            tail = items[:idx] + items[idx + 1:]
            for rest in self._permutations(tail):
                yield (head,) + rest

    # ------------------------------------------- 最短哈密顿路径（递归回溯）

    def shortest_hamiltonian_backtrack(self, dist, start=0):
        """独立做法：递归回溯逐点扩展，遇更优前缀才继续。"""
        self._reset_counts()
        if self._size == 0:
            raise GraphErro("没有点，无法求哈密顿路径")
        self._check_square(dist, "dist")
        self._check_start(start)
        best = [None, None]

        def walk(path, used, cost):
            if len(path) == self._size:
                self.backtrack_visits += 1
                cand = tuple(path)
                if best[0] is None or cost < best[0] or (cost == best[0] and cand < best[1]):
                    best[0] = cost
                    best[1] = cand
                return
            last = path[-1]
            for nxt in range(self._size):
                if used & (1 << nxt):
                    continue
                used |= 1 << nxt
                path.append(nxt)
                walk(path, used, cost + dist[last][nxt])
                path.pop()
                used &= ~(1 << nxt)

        walk([start], 1 << start, 0)
        return best[0], list(best[1])

    # --------------------------------------------- 最短哈密顿回路（朴素）

    def shortest_cycle(self, dist, start=0):
        """从 start 出发回到 start 的最短回路，返回（代价，路径）。

        路径以 start 开头并以 start 结尾，并列时取字典序最小。朴素枚举全排列。
        """
        self._reset_counts()
        if self._size < 2:
            raise GraphErro("回路至少需要两个点")
        self._check_square(dist, "dist")
        self._check_start(start)
        rest = [i for i in range(self._size) if i != start]
        best_cost = None
        best_path = None
        for perm in self._permutations(rest):
            path = (start,) + perm + (start,)
            cost = 0
            for k in range(len(path) - 1):
                cost += dist[path[k]][path[k + 1]]
            self.perm_visits += 1
            if best_cost is None or cost < best_cost or (cost == best_cost and path < best_path):
                best_cost = cost
                best_path = path
        return best_cost, list(best_path)

    # -------------------------------------- 集合覆盖（枚举全部子集组合）

    def min_cover(self, target, subsets):
        """用 subsets 盖住 target 的最少个数与一组方案，返回（个数，下标列表）。

        下标列表升序，并列时取字典序最小。无方案报 CoverErro。朴素做法按
        个数从小到大枚举全部组合。
        """
        self._reset_counts()
        masks = self._check_subsets(target, subsets)
        if target == 0:
            return 0, []
        n = len(masks)
        best = None
        for k in range(1, n + 1):
            for combo in self._combinations(range(n), k):
                self.cover_visits += 1
                union = 0
                for idx in combo:
                    union |= masks[idx]
                if union == target:
                    if best is None:
                        best = list(combo)
                    break
            if best is not None:
                return len(best), best
        raise CoverErro("不存在覆盖方案")

    def _combinations(self, pool, k):
        """生成 pool 的全部 k 元组合，朴素递归。"""
        if k == 0:
            yield ()
            return
        for i in range(len(pool) - k + 1):
            head = pool[i]
            for rest in self._combinations(pool[i + 1:], k - 1):
                yield (head,) + rest

    def _check_subsets(self, target, subsets):
        if not _is_int(target) or target < 0 or target > self.full_mask():
            raise CoverErro("目标集合掩码越界：%r" % (target,))
        if not isinstance(subsets, (list, tuple)):
            raise CoverErro("subsets 必须是序列")
        masks = []
        for m in subsets:
            if not _is_int(m) or m < 0 or m > self.full_mask():
                raise CoverErro("子集掩码越界：%r" % (m,))
            masks.append(m)
        return masks

    # -------------------------------------- 集合覆盖（独立递归回溯）

    def min_cover_backtrack(self, target, subsets):
        """独立做法：递归选或不选，记录当前已盖住的部分并按最优剪枝。"""
        self._reset_counts()
        masks = self._check_subsets(target, subsets)
        best = [None]

        def walk(idx, covered, chosen):
            if covered == target:
                self.backtrack_visits += 1
                cand = tuple(chosen)
                if best[0] is None or len(cand) < len(best[0]) or (
                        len(cand) == len(best[0]) and cand < best[0]):
                    best[0] = cand
                return
            if idx == len(masks):
                return
            if best[0] is not None and len(chosen) > len(best[0]):
                return
            walk(idx + 1, covered | masks[idx], chosen + [idx])
            walk(idx + 1, covered, chosen)

        walk(0, 0, [])
        if best[0] is None:
            raise CoverErro("不存在覆盖方案")
        return len(best[0]), list(best[0])

    # ----------------------------------------- 最优划分（枚举全部划分）

    def min_groups(self, related):
        """把全部元素分成若干组，每组内两两相容的最少组数与划分方案。

        related[i][j] 为 1 表示 i 与 j 可同组。返回（组数，组列表），每组为升序
        下标元组，组按首元素升序排列，并列时取该规范形字典序最小的划分。
        朴素做法递归枚举全部集合划分。
        """
        self._reset_counts()
        self._check_related(related)
        n = self._size
        if n == 0:
            return 0, []
        best = [None, None]

        def recurse(i, assign, maxg):
            if i == n:
                self.partition_visits += 1
                part = self._canonical(assign)
                if part is None:
                    return
                if not self._all_related(part, related):
                    return
                count = len(part)
                if best[0] is None or count < best[0] or (count == best[0] and part < best[1]):
                    best[0] = count
                    best[1] = part
                return
            for g in range(maxg + 1):
                assign[i] = g
                recurse(i + 1, assign, maxg)
            assign[i] = maxg + 1
            recurse(i + 1, assign, maxg + 1)

        recurse(0, [-1] * n, 0)
        return best[0], [list(g) for g in best[1]]

    def _canonical(self, assign):
        groups = {}
        for i, g in enumerate(assign):
            groups.setdefault(g, []).append(i)
        parts = [tuple(sorted(v)) for v in groups.values()]
        parts.sort(key=lambda g: g[0])
        return tuple(parts)

    def _all_related(self, part, related):
        for group in part:
            for a in range(len(group)):
                for b in range(a + 1, len(group)):
                    if not related[group[a]][group[b]]:
                        return False
        return True

    def _check_related(self, related):
        n = self._size
        if not isinstance(related, (list, tuple)) or len(related) != n:
            raise GraphErro("related 必须是 %d 行" % n)
        for i, row in enumerate(related):
            if not isinstance(row, (list, tuple)) or len(row) != n:
                raise GraphErro("related 每行必须是 %d 个元素" % n)
            for j, value in enumerate(row):
                if not _is_int(value) or value not in (0, 1):
                    raise GraphErro("related 只能是 0 或 1：%r" % (value,))
                if i == j and value != 1:
                    raise GraphErro("对角线必须是 1")
        for i in range(n):
            for j in range(i + 1, n):
                if related[i][j] != related[j][i]:
                    raise GraphErro("related 必须对称")

    # ----------------------------------------- 最优划分（独立递归回溯）

    def min_groups_backtrack(self, related):
        """独立做法：逐个元素放入已相容的组或另开新组，按当前组数剪枝。"""
        self._reset_counts()
        self._check_related(related)
        n = self._size
        if n == 0:
            return 0, []
        best = [None, None]

        def walk(i, groups):
            if i == n:
                self.backtrack_visits += 1
                part = tuple(sorted((tuple(sorted(g)) for g in groups), key=lambda g: g[0]))
                count = len(part)
                if best[0] is None or count < best[0] or (count == best[0] and part < best[1]):
                    best[0] = count
                    best[1] = part
                return
            if best[0] is not None and len(groups) > best[0]:
                return
            for g in groups:
                if all(related[i][m] for m in g):
                    g.append(i)
                    walk(i + 1, groups)
                    g.pop()
            groups.append([i])
            walk(i + 1, groups)
            groups.pop()

        walk(0, [])
        return best[0], [list(g) for g in best[1]]
