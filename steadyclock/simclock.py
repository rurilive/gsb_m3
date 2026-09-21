"""对端时钟与往返链路的模拟。

一次往返里本地打两个戳（发出、收到），对端打两个戳（收到、发出），
四个戳合起来能同时算出两端钟差与往返时延。这个模块把那一趟做成可控的
模拟：Link 抽两条单向时延与错误样本，PeerClock 是对端的墙上钟，
Loopback 把一次往返拼成四个时间戳交出去。

对端墙上钟挂在本地单调时间轴上：给一个本地单调时刻，读回对端此刻的
墙上钟。时延、尖峰、对端错读都由 Link 的参数控制，随机数走 seed，
同一条链路按顺序抽的签可复现。
"""

import random


class PeerClock:
    """对端的墙上钟：跟本机时钟同一个时间基准，差一个固定残差。

    true_offset 是本次模拟注入的真值，drift 按时间轴零点起算的每秒
    偏移量。读数挂在本地单调时间轴上，本机墙钟被校时拨动不影响它。
    """

    def __init__(self, true_offset=0.0, drift=0.0):
        self.true_offset = float(true_offset)
        self.drift = float(drift)

    def wall_at(self, local_monotonic):
        """对端在本地单调时刻 local_monotonic 的墙上读数。"""
        return (
            float(local_monotonic)
            + self.true_offset
            + self.drift * float(local_monotonic)
        )


class Link:
    """两条单向链路：请求与响应各抽一条时延，另有尖峰与错误样本。

    两条时延都从 base_delay 起，各加一段 [0, jitter) 的随机；响应方向
    再叠一个固定的 skew，用来模拟上下行不对称。spike_chance 的机会里
    随机挑一条方向乘上 spike_factor，模拟排队尖峰；fault_chance 的机会
    里对端整趟读数错误，两个戳一起偏 fault_shift。
    """

    def __init__(
        self,
        base_delay=0.02,
        jitter=0.004,
        skew=0.0,
        spike_chance=0.0,
        spike_factor=25.0,
        fault_chance=0.0,
        fault_shift=1800.0,
        seed=None,
    ):
        self._base_delay = float(base_delay)
        self._jitter = float(jitter)
        self._skew = float(skew)
        self._spike_chance = float(spike_chance)
        self._spike_factor = float(spike_factor)
        self._fault_chance = float(fault_chance)
        self._fault_shift = float(fault_shift)
        self._random = random.Random(seed)
        self.spikes = 0
        self.faults = 0

    def plan(self):
        """给一次往返抽签，返回 (请求时延, 响应时延, 对端读数偏移)。

        第三条平时是 0.0，抽中错误样本时是 fault_shift，这趟对端的两
        个读数一起偏这么多。
        """
        request = self._base_delay + self._random.uniform(0.0, self._jitter)
        response = (
            self._base_delay + self._random.uniform(0.0, self._jitter) + self._skew
        )
        if self._spike_chance and self._random.random() < self._spike_chance:
            if self._random.random() < 0.5:
                request *= self._spike_factor
            else:
                response *= self._spike_factor
            self.spikes += 1
        fault = 0.0
        if self._fault_chance and self._random.random() < self._fault_chance:
            fault = self._fault_shift
            self.faults += 1
        return request, response, fault


class Loopback:
    """本机与对端之间的一次往返，产出四个时间戳。

    t0 本地发出、t1 对端收到、t2 对端发出、t3 本地收到，单位都是秒，
    前两个跟后两个各在各家的时间轴上。往返期间本地时间由 source.sleep
    推进，推进的长度就是两条单向时延加对端的处理耗时 service。
    """

    def __init__(self, source, peer, link, service=0.0005):
        self._source = source
        self._peer = peer
        self._link = link
        self._service = float(service)

    def _local_stamp(self):
        """本地这一端的读数，走单调钟，校时拨不动。"""
        return self._source.monotonic()

    def exchange(self):
        """跑一次往返，返回 (t0, t1, t2, t3) 四个时间戳。"""
        request, response, fault = self._link.plan()
        t0 = self._local_stamp()
        t1 = self._peer.wall_at(self._source.monotonic() + request) + fault
        t2 = (
            self._peer.wall_at(self._source.monotonic() + request + self._service)
            + fault
        )
        self._source.sleep(request + self._service + response)
        t3 = self._local_stamp()
        return (t0, t1, t2, t3)
