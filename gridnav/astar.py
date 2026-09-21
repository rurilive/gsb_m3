"""A* 寻路与障碍变更后的增量修路：AStarPlanner。

启发式用对角线距离（octile）：横竖一步 1.0、斜一步 SQRT2 时的可采纳
下界。启发式是浮点运算，为防止舍入把估计值顶过真实代价，整体乘以
HEURISTIC_SCALE = 1.0 - 1e-12 略微下压；开放列表里的比较直接用浮点
<，不做额外舍入。这些规则由 tests/test_astar.py 锁死。

AStarPlanner 缓存最近一次查询与当时的障碍快照：replan 时若障碍没动、
或只增不减且新增阻塞没压到缓存路径上，直接复用旧结果（可证仍最优），
不展开任何节点；只有路径被压断时才从断点起做局部 A* 修复。stats()
里的累计展开数可以印证这一点。
"""

import heapq

from gridnav.grid import DIRECTIONS, SQRT2, GridError  # noqa: F401

HEURISTIC_SCALE = 1.0 - 1e-12


def heuristic(x, y, gx, gy):
    """(x, y) 到 (gx, gy) 的对角线启发式：可采纳、确定、跨进程一致。"""
    dx = abs(x - gx)
    dy = abs(y - gy)
    if dx < dy:
        dx, dy = dy, dx
    return (dx + (SQRT2 - 1.0) * dy) * HEURISTIC_SCALE


class AStarPlanner:
    """绑定一张 Grid 的 A* 规划器，支持 set_blocked 后的增量修复。"""

    def __init__(self, grid):
        self._grid = grid
        self._expansions = 0
        self._full_searches = 0
        self._repairs = 0
        self._reuses = 0
        self._last_query = None
        self._last_path = None
        self._snapshot = None

    # -- 查询 --------------------------------------------------

    def plan(self, start, goal):
        """A* 最短路（含起终点），不可达返回 None。

        起点或终点越界、被堵抛 GridError。每次调用都做完整搜索并重置
        增量缓存；代价并列时按 (-g, (x, y)) 决定出堆顺序，结果可复现。
        """
        start = self._grid.require_cell(start, "start")
        goal = self._grid.require_cell(goal, "goal")
        path = self._search(start, goal)
        self._full_searches += 1
        self._remember(start, goal, path)
        return path

    def replan(self, start, goal):
        """障碍变更后的增量修路：返回语义同 plan，但尽量复用上次结果。

        - 查询与上次不同、或上次之后有格子被解除阻塞：退回完整搜索；
        - 障碍没变化、或只增不减且没压到缓存路径（含上次已不可达）：
          直接复用，不展开任何节点；
        - 新增阻塞压断缓存路径：保留断点前缀，从断点前一格起做局部
          A* 接到 goal，只重算受影响的一段。
        """
        start = self._grid.require_cell(start, "start")
        goal = self._grid.require_cell(goal, "goal")
        if self._last_query != (start, goal) or self._snapshot is None:
            path = self._search(start, goal)
            self._full_searches += 1
        else:
            current = set(self._grid.blocked_cells())
            added = current - self._snapshot
            removed = self._snapshot - current
            path = self._last_path
            if removed:
                # 解除阻塞可能开出更短的路，局部修复保证不了最优，退回全搜。
                path = self._search(start, goal)
                self._full_searches += 1
            elif not added or path is None:
                # 只加堵时，旧路径（含 None）不可能变得更差。
                self._reuses += 1
            elif not any(cell in added for cell in path):
                self._reuses += 1
            else:
                cut = next(i for i, cell in enumerate(path) if cell in added)
                prefix = path[:cut]
                suffix = self._search(prefix[-1], goal)
                self._repairs += 1
                path = None if suffix is None else prefix + suffix[1:]
        self._remember(start, goal, path)
        return path

    def stats(self):
        """累计统计快照，键：expansions / full_searches / repairs / reuses。

        expansions 是历次搜索累计展开的节点数，是判断增量修复是否只
        重算受影响段的依据。
        """
        return {
            "expansions": self._expansions,
            "full_searches": self._full_searches,
            "repairs": self._repairs,
            "reuses": self._reuses,
        }

    # -- 内部 --------------------------------------------------

    def _remember(self, start, goal, path):
        self._last_query = (start, goal)
        self._last_path = path
        # 同包内直接读阻塞集合，省掉 blocked_cells() 的排序开销。
        self._snapshot = set(self._grid._blocked)

    def _search(self, start, goal):
        """标准 A*：开放列表为堆，条目 (f, -g, cell) 让并列出堆可复现。"""
        if start == goal:
            return [start]
        grid = self._grid
        gx, gy = goal
        # 邻居枚举内联展开（规则与 Grid.neighbors 一致），热循环少一次
        # 方法调用和一层元组打包；blocked 同样是同包内的快速通道。
        blocked = grid._blocked
        width = grid.width
        height = grid.height
        g_score = {start: 0.0}
        parent = {start: None}
        heap = [(heuristic(start[0], start[1], gx, gy), 0.0, start)]
        closed = set()
        inf = float("inf")
        while heap:
            _f, _neg_g, cur = heapq.heappop(heap)
            if cur in closed:
                continue
            closed.add(cur)
            self._expansions += 1
            if cur == goal:
                break
            gc = g_score[cur]
            x, y = cur
            for dx, dy in DIRECTIONS:
                nx = x + dx
                ny = y + dy
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                nxt = (nx, ny)
                if nxt in blocked or nxt in closed:
                    continue
                if dx != 0 and dy != 0:
                    if (x + dx, y) in blocked and (x, y + dy) in blocked:
                        continue
                    ng = gc + SQRT2
                else:
                    ng = gc + 1.0
                if ng < g_score.get(nxt, inf):
                    g_score[nxt] = ng
                    parent[nxt] = cur
                    heapq.heappush(
                        heap, (ng + heuristic(nx, ny, gx, gy), -ng, nxt))
        if goal not in parent:
            return None
        path = []
        cur = goal
        while cur is not None:
            path.append(cur)
            cur = parent[cur]
        path.reverse()
        return path
