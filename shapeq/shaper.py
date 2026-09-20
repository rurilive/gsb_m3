"""令牌桶流量整形与多租户公平。

与 FixedWindowLimiter 并存，互不影响：

- 令牌按 refill_rate（个/秒）持续补充、上限为 capacity，短突发由桶内
  存量令牌吸收，平时按速率放行。
- 每个租户有独立令牌桶，另有一个所有租户共享的全局桶代表后端总配额；
  一次放行必须同时拿到租户令牌与全局令牌，因此单个租户最多只能按自己
  的速率/容量消耗共享额度，打满也吃不掉别人的那份。
- 超出的请求按策略处理：REJECT 立即拒绝；QUEUE 按令牌补充节奏排队等待，
  超过等待上限同样拒绝。

时间全部取自注入时钟，等待通过注入的 sleep 完成，测试用假时钟即可
精确对齐补充点，不依赖真实时间。
"""

import threading
import time


REJECT = "reject"
QUEUE = "queue"


class ShaperDecision:
    """acquire 的结果。

    status:
      - "allowed" 拿到令牌；QUEUE 下可能经过 wait，waited 为实际等待秒数
      - "queued" 已入队但还没等到（仅 try_acquire 可能返回）
      - "rejected" 被拒；reason 为 "rate_limited"（REJECT 策略）或
        "wait_timeout"（排队超过等待上限）
    """

    __slots__ = ("tenant", "status", "reason", "ready_at", "waited")

    def __init__(self, tenant, status, reason=None, ready_at=None, waited=0.0):
        self.tenant = tenant
        self.status = status
        self.reason = reason
        self.ready_at = ready_at
        self.waited = waited

    @property
    def allowed(self):
        return self.status == "allowed"

    def __repr__(self):
        return (
            f"ShaperDecision(tenant={self.tenant!r}, status={self.status!r}, "
            f"reason={self.reason!r}, ready_at={self.ready_at}, waited={self.waited})"
        )


class _Bucket:
    """惰性补充的令牌桶，且支持在将来某个时刻预扣一个令牌。

    已排队但未生效的预扣记在 debits（时刻列表，升序）里。
    balance/anchor 只反映最早一笔未生效预扣之前的状态：查询可放行
    时刻时逐笔预扣推进，从而给后来的请求让出正确的补充点。
    """

    __slots__ = ("capacity", "rate", "balance", "anchor", "debits")

    def __init__(self, capacity, rate, now):
        self.capacity = float(capacity)
        self.rate = float(rate)
        self.balance = float(capacity)
        self.anchor = now
        self.debits = []

    def refill(self, now):
        """按当前时刻补充，并结算已到期的预扣。"""
        balance = self.balance
        cursor = self.anchor
        remaining = []
        for at in self.debits:
            if at <= now:
                balance = min(
                    self.capacity, balance + (at - cursor) * self.rate
                )
                balance -= 1.0
                cursor = at
            else:
                remaining.append(at)
        balance = min(self.capacity, balance + (now - cursor) * self.rate)
        self.balance = balance
        self.anchor = now
        self.debits = remaining

    def slot_after(self, not_before):
        """在不修改状态的前提下，给出下一个令牌最早可用时刻（>= not_before）。"""
        balance = self.balance
        cursor = self.anchor
        t = not_before
        index = 0
        debits = self.debits
        # 先把不晚于 t 的已预约令牌按时间顺序结算掉（含其间的补充）。
        while index < len(debits) and debits[index] <= t:
            debit_at = debits[index]
            balance = min(
                self.capacity, balance + (debit_at - cursor) * self.rate
            )
            balance -= 1.0
            cursor = debit_at
            index += 1
        balance = min(self.capacity, balance + (t - cursor) * self.rate)
        if balance >= 1.0:
            return t
        # 之后逐笔已有预约竞争：同一时刻预约排队在先，新请求需再攒出一个。
        for debit_at in debits[index:]:
            balance = min(
                self.capacity, balance + (debit_at - t) * self.rate
            )
            t = debit_at
            if balance >= 2.0:
                return t
            balance -= 1.0
        return t + (1.0 - balance) / self.rate

    def reserve(self, at):
        """把时刻 at 的预扣登记进桶（调用前须保证 slot 计算覆盖到 at）。"""
        self.debits.append(at)
        self.debits.sort()


class TokenBucketShaper:
    """两级令牌桶整形器：租户桶限速 + 全局桶保护共享后端配额。

    capacity / refill_rate：每个租户桶的容量与补充速率（个/秒）。
    global_capacity / global_refill_rate：共享全局桶；不传时只做
      每租户独立整形，不存在共享上限。
    policy：REJECT（默认，没令牌立即拒）或 QUEUE（排队等令牌）。
    max_wait：QUEUE 下允许等待的最长秒数，等不到以 wait_timeout 拒绝。
    clock / sleep：注入时钟与等待函数，测试可接手动时钟。
    """

    REJECT = REJECT
    QUEUE = QUEUE

    def __init__(
        self,
        capacity,
        refill_rate,
        global_capacity=None,
        global_refill_rate=None,
        policy=REJECT,
        max_wait=1.0,
        clock=time.monotonic,
        sleep=time.sleep,
    ):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be > 0")
        if global_capacity is not None and global_capacity < 1:
            raise ValueError("global_capacity must be >= 1")
        if global_refill_rate is not None and global_refill_rate <= 0:
            raise ValueError("global_refill_rate must be > 0")
        if (global_capacity is None) != (global_refill_rate is None):
            raise ValueError(
                "global_capacity and global_refill_rate must be given together"
            )
        if policy not in (REJECT, QUEUE):
            raise ValueError("policy must be REJECT or QUEUE")
        if max_wait < 0:
            raise ValueError("max_wait must be >= 0")
        self._capacity = capacity
        self._rate = refill_rate
        self._global_capacity = global_capacity
        self._global_rate = global_refill_rate
        self._policy = policy
        self._max_wait = float(max_wait)
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._tenants = {}
        self._global = (
            _Bucket(global_capacity, global_refill_rate, clock())
            if global_capacity is not None
            else None
        )
        # (tenant_bucket, decision) 对，按可放行时刻有序
        self._waiting = []
        self._allowed = 0
        self._rejected = 0

    def _settle(self, now):
        """结算所有桶并放行已到点的排队请求，返回仍在等待的队列。"""
        for bucket in self._tenants.values():
            bucket.refill(now)
        if self._global is not None:
            self._global.refill(now)
        still = []
        for bucket, decision in self._waiting:
            if decision.ready_at <= now:
                decision.status = "allowed"
                self._allowed += 1
            else:
                still.append((bucket, decision))
        self._waiting = still
        return still

    def try_acquire(self, tenant):
        """非阻塞申请：立即有令牌则放行，否则按策略拒绝或入队。

        返回 ShaperDecision。QUEUE 下入队的请求 status 为 "queued"，
        ready_at 为预计可放行时刻；之后用 wait 等结果。
        """
        with self._lock:
            now = self._clock()
            self._settle(now)

            bucket = self._tenants.get(tenant)
            if bucket is None:
                bucket = _Bucket(self._capacity, self._rate, now)
                self._tenants[tenant] = bucket

            # 两级桶互相推延，迭代到双方的最早可放行时刻一致。
            ready = now
            while True:
                candidate = bucket.slot_after(ready)
                if self._global is not None:
                    candidate = max(
                        candidate, self._global.slot_after(ready)
                    )
                if candidate <= ready:
                    break
                ready = candidate

            if ready > now:
                if self._policy is REJECT:
                    self._rejected += 1
                    return ShaperDecision(
                        tenant, "rejected", reason="rate_limited"
                    )
                if ready - now > self._max_wait:
                    self._rejected += 1
                    return ShaperDecision(
                        tenant,
                        "rejected",
                        reason="wait_timeout",
                        ready_at=ready,
                    )
                bucket.reserve(ready)
                if self._global is not None:
                    self._global.reserve(ready)
                decision = ShaperDecision(
                    tenant, "queued", ready_at=ready
                )
                self._waiting.append((bucket, decision))
                self._waiting.sort(key=lambda item: item[1].ready_at)
                return decision

            bucket.balance -= 1.0
            if self._global is not None:
                self._global.balance -= 1.0
            self._allowed += 1
            return ShaperDecision(tenant, "allowed", ready_at=now, waited=0.0)

    def wait(self, decision):
        """等待一个 queued 决定出结果，返回同一个 decision。"""
        if decision.status != "queued":
            return decision
        delay = decision.ready_at - self._clock()
        if delay > 0:
            decision.waited += delay
            self._sleep(delay)
        with self._lock:
            self._settle(self._clock())
        return decision

    def acquire(self, tenant):
        """申请一个令牌；QUEUE 策略下会阻塞等到放行或超过等待上限。"""
        decision = self.try_acquire(tenant)
        if decision.status == "queued":
            self.wait(decision)
        return decision

    def stats(self):
        """计数与实时状态快照，返回独立 dict，调用方随便改。

        tokens：每个租户桶当前剩余令牌（已含补充、已扣预占）；
        global_tokens：共享桶剩余令牌，无共享桶时为 None；
        queued：当前排队长度；allowed/rejected 为累计计数。
        """
        with self._lock:
            now = self._clock()
            self._settle(now)
            return {
                "allowed": self._allowed,
                "rejected": self._rejected,
                "queued": len(self._waiting),
                "tokens": {
                    tenant: bucket.balance
                    for tenant, bucket in self._tenants.items()
                },
                "global_tokens": (
                    self._global.balance if self._global is not None else None
                ),
            }
