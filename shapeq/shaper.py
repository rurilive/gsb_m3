"""令牌桶流量整形 + 多租户公平调度。

与 FixedWindowLimiter 并存，互不影响：每个租户一个独立令牌桶，
桶容量 capacity 吸收突发，按 rate（令牌/秒）持续补充。租户之间
不共享令牌，因此任何租户都只能打满自己那份，饿不到别人。

超出时按 overflow 策略处理：
- REJECT：立刻拒绝；
- QUEUE：按 FIFO 排队等待补充；超过 max_wait 或 max_queue 时拒绝。
"""

from collections import deque
import threading
import time


REJECT = "reject"
QUEUE = "queue"

_ALLOWED = "allowed"
_QUEUED = "queued"
_REJECTED = "rejected"


class AcquireResult:
    """一次申请的结果。

    status 为 allowed / queued / rejected；队列模式下 wait 会把
    queued 更新为终态 allowed / rejected。reason 给出拒绝原因。
    """

    def __init__(self, status, reason=None, waited=0.0, ticket=None):
        self.status = status
        self.reason = reason
        self.waited = waited
        self._ticket = ticket

    @property
    def allowed(self):
        return self.status == _ALLOWED

    @property
    def queued(self):
        return self.status == _QUEUED

    def wait(self, timeout=None):
        """队列模式下阻塞等结果，返回 self；其余策略立即返回。"""
        if self._ticket is not None:
            ticket = self._ticket
            ticket["event"].wait(timeout)
            self.status = ticket["status"]
            self.reason = ticket["reason"]
            if ticket["status"] != _QUEUED:
                self.waited = max(0.0, ticket["finished_at"] - ticket["created_at"])
            self._ticket = None
        return self

    def __repr__(self):
        return f"AcquireResult(status={self.status!r}, reason={self.reason!r}, waited={self.waited:.3f})"


class TokenBucketShaper:
    """每租户独立令牌桶的整形器。

    rate: 每个租户每秒补充的令牌数，必须为正。
    capacity: 每个租户的桶容量（可吸收的突发上限），必须为正。
    overflow: REJECT（默认，超出立即拒绝）或 QUEUE（排队等待）。
    max_wait: QUEUE 模式下单个请求最长等待秒数，None 表示不限制。
    max_queue: 排队总数上限，None 表示不限制。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(self, rate, capacity, overflow=REJECT,
                 max_wait=None, max_queue=None, clock=time.monotonic):
        if rate <= 0:
            raise ValueError("rate must be > 0")
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        if overflow not in (REJECT, QUEUE):
            raise ValueError("overflow must be REJECT or QUEUE")
        if max_wait is not None and max_wait < 0:
            raise ValueError("max_wait must be >= 0")
        if max_queue is not None and max_queue < 0:
            raise ValueError("max_queue must be >= 0")
        self._rate = float(rate)
        self._capacity = float(capacity)
        self._overflow = overflow
        self._max_wait = max_wait
        self._max_queue = max_queue
        self._clock = clock
        self._lock = threading.Lock()
        # tenant -> {"tokens": float, "updated": float, "queue": deque[ticket]}
        self._tenants = {}
        self._allowed = 0
        self._rejected = 0
        self._queued = 0
        self._scheduler_started = False

    def _refill(self, state, now):
        """惰性补充：把上次更新到 now 之间产生的令牌加回桶里。"""
        elapsed = now - state["updated"]
        if elapsed > 0:
            state["tokens"] = min(self._capacity, state["tokens"] + elapsed * self._rate)
            state["updated"] = now

    def acquire(self, tenant, amount=1):
        """为 tenant 申请 amount 个令牌，返回 AcquireResult。"""
        if amount <= 0:
            raise ValueError("amount must be > 0")
        with self._lock:
            now = self._clock()
            state = self._tenants.get(tenant)
            if state is None:
                state = {"tokens": self._capacity, "updated": now, "queue": None}
                self._tenants[tenant] = state
            self._refill(state, now)

            if state["queue"]:
                # 队列里有人排队，新来的不能插队，直接按排队路径处理。
                return self._enqueue(state, amount, now)
            if state["tokens"] + 1e-9 >= amount:
                state["tokens"] -= amount
                self._allowed += 1
                return AcquireResult(_ALLOWED)
            if self._overflow == REJECT:
                self._rejected += 1
                return AcquireResult(_REJECTED, reason="rate_limited")
            return self._enqueue(state, amount, now)

    def _enqueue(self, state, amount, now):
        """调用方持锁。把请求排进该租户的 FIFO，超限则拒绝。"""
        queue = state["queue"]
        if queue is None:
            queue = state["queue"] = deque()

        deficit = amount - state["tokens"]
        wait_for_tokens = max(0.0, deficit) / self._rate
        # FIFO：必须排在队尾之后，ready_at 取队尾就绪时刻。
        ready_at = now + wait_for_tokens
        if queue:
            ready_at = max(ready_at, queue[-1]["ready_at"])

        if self._max_queue is not None and self._queued >= self._max_queue:
            self._rejected += 1
            return AcquireResult(_REJECTED, reason="queue_full")
        if self._max_wait is not None and ready_at - now > self._max_wait + 1e-9:
            self._rejected += 1
            return AcquireResult(_REJECTED, reason="max_wait_exceeded")

        ticket = {
            "amount": amount,
            "ready_at": ready_at,
            "created_at": now,
            "finished_at": now,
            "status": _QUEUED,
            "reason": None,
            "event": threading.Event(),
        }
        # 预占令牌：桶转成负值（欠账），补充优先还债。
        state["tokens"] -= amount
        queue.append(ticket)
        self._queued += 1
        self._ensure_scheduler()
        return AcquireResult(_QUEUED, ticket=ticket)

    def pump(self, now=None):
        """处理当前时钟下已经到期的排队请求。

        注入时钟的测试里推进时钟后手动调用；真实时钟下后台调度
        线程会自动 pump，无需调用。返回本次放行的请求数。
        """
        served = 0
        with self._lock:
            if now is None:
                now = self._clock()
            for state in self._tenants.values():
                queue = state["queue"]
                if not queue:
                    continue
                self._refill(state, now)
                while queue and queue[0]["ready_at"] <= now + 1e-9:
                    ticket = queue.popleft()
                    ticket["status"] = _ALLOWED
                    ticket["finished_at"] = now
                    ticket["event"].set()
                    self._queued -= 1
                self._allowed += 1
                served += 1
        return served

    def _ensure_scheduler(self):
        """真实时钟场景下起一个守护线程，到点自动 pump。"""
        if self._clock is time.monotonic and not self._scheduler_started:
            self._scheduler_started = True
            thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            thread.start()

    def _scheduler_loop(self):
        while True:
            time.sleep(0.01)
            now = time.monotonic()
            with self._lock:
                if not self._tenants:
                    continue
                next_ready = None
                for state in self._tenants.values():
                    if state["queue"]:
                        head = state["queue"][0]["ready_at"]
                        next_ready = head if next_ready is None else min(next_ready, head)
                if next_ready is None:
                    continue
                if next_ready > now:
                    continue
            self.pump(now)

    def stats(self):
        """计数快照，返回独立 dict，调用方随便改。"""
        with self._lock:
            tokens = {}
            for tenant, state in self._tenants.items():
                self._refill(state, self._clock())
                tokens[tenant] = max(0.0, state["tokens"])
            return {
                "allowed": self._allowed,
                "rejected": self._rejected,
                "queued": self._queued,
                "tokens_remaining": sum(tokens.values()),
                "tokens_by_tenant": tokens,
                "tenants": len(self._tenants),
            }
