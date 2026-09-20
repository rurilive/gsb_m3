"""带租约的主备选举：主必须定期续租，续不上就认输让位。

安全设计（详见 README「实现说明」）：
- 本地租约有效性只看单调时钟：距上次成功续租超过 lease_duration 即自认出局，
  GC 停顿、墙钟回拨都骗不过单调时钟。
- 候选者不比墙钟时间戳，而是观察到租约记录静止满一个 lease_duration 才接手；
  宁可短暂无主，也不冒双主。
- 每次换主 fencing token 加一，存储层凭 token 挡住过期主的写入。
"""
import fcntl
import json
import os
import threading
import time

_CORRUPT = object()  # 读出来无法解析的记录，按「状况不明」保守处理


class LeaseLostError(Exception):
    """租约已失效：当前节点不再是主，必须停止写入。"""


class StaleFencingTokenError(Exception):
    """写入携带的 fencing token 已过期，被存储层拒绝。"""


class LeaseElection:
    """带租约的选主器。

    try_acquire() 在租约记录静止满一个 lease_duration 后才接手；renew() 续租；
    is_primary() 只查本地单调时钟、无 IO，可放在业务写入路径上；
    assert_primary() 在写入前把关，返回随主走的 fencing token。
    """

    def __init__(self, path, node_id, lease_duration=10.0, renew_interval=None,
                 clock=time.monotonic, wall_clock=time.time):
        self._path = path
        self._node_id = node_id
        self._lease_duration = float(lease_duration)
        self._renew_interval = (float(renew_interval) if renew_interval
                                else self._lease_duration / 3.0)
        self._clock = clock            # 单调时钟，所有安全判断只信它
        self._wall_clock = wall_clock  # 墙钟只用于记录里的展示字段
        self._token = None
        self._seq = 0
        self._last_renew_ok = None     # 上次成功续租的单调时刻
        self._observed = None          # 候选者视角：(记录指纹, 首次看到的单调时刻)
        self._state = {}
        self._mu = threading.RLock()
        self._stop = threading.Event()
        self._thread = None

    @property
    def node_id(self):
        return self._node_id

    @property
    def fencing_token(self):
        """当前主的 fencing token；不是主时为 None。"""
        return self._token if self.is_primary() else None

    def is_primary(self):
        """是否仍在租约有效期内。纯本地单调时钟判断，无 IO。"""
        return (self._token is not None
                and self._clock() - self._last_renew_ok < self._lease_duration)

    def try_acquire(self):
        """尝试成为主。记录被活人持有、或静止时间还不够时返回 False。"""
        with self._mu:
            if self.is_primary():
                return True
            try:
                record = self._read_record()
            except OSError:
                return False
            if record is _CORRUPT:
                return False  # 状况不明，宁可无主
            now = self._clock()
            if record is not None and record.get("holder") is not None:
                key = self._key(record)
                if self._observed is None or self._observed[0] != key:
                    self._observed = (key, now)  # 第一次看到这份记录，开始计时
                    return False
                if now - self._observed[1] < self._lease_duration:
                    return False                 # 静止未满一个租约期，继续等
            token = (record["token"] if record else 0) + 1
            state = dict(record.get("state", {})) if record else {}
            try:
                result = self._fenced_update(
                    lambda cur: self._key(cur) == self._key(record),
                    holder=self._node_id, token=token, seq=0, state=state)
            except OSError:
                return False
            if result != "ok":
                return False                     # 有人抢先，下轮重新观察
            self._token = token
            self._seq = 0
            self._state = state
            self._last_renew_ok = now
            self._observed = None
            return True

    def renew(self):
        """续租一次。成功返回 True；失败返回 False。

        单次失败（IO 抖动）不丢主位，只要在租约截止前续上就没事；
        若本地租约已过期、或发现记录已属他人，立即认输。
        """
        with self._mu:
            if self._token is None:
                return False
            if not self.is_primary():
                self._forfeit()  # 本地租约已过期，认输，不许续命
                return False
            new_seq = self._seq + 1
            try:
                result = self._fenced_update(
                    self._still_mine, holder=self._node_id,
                    token=self._token, seq=new_seq, state=self._state)
            except OSError:
                return False     # 抖动，交给本地截止时间兜底
            if result == "ok":
                self._seq = new_seq
                self._last_renew_ok = self._clock()
                return True
            self._forfeit()      # 记录已属他人，立即认输
            return False

    def release(self):
        """主动让位：写让位标记，备机可立即接手，不必等满静止窗口。"""
        self.stop()
        with self._mu:
            if self._token is None:
                return
            try:
                self._fenced_update(self._still_mine, holder=None,
                                    token=self._token, seq=self._seq + 1,
                                    state=self._state)
            except OSError:
                pass             # 标记写不进去也不影响安全：token 已带走
            self._forfeit()

    def assert_primary(self):
        """写入前的把关：仍是主则返回 fencing token，否则抛 LeaseLostError。"""
        if not self.is_primary():
            raise LeaseLostError("node %s 的租约已失效" % self._node_id)
        return self._token

    def update_state(self, state):
        """更新交接状态；是主时立即尽力写进租约记录，返回是否落盘。"""
        with self._mu:
            self._state.update(state)
            if not self.is_primary():
                return False
            return self.renew()

    def handover_state(self):
        """读出租约记录里携带的交接状态（新主接手后从这里继续）。"""
        try:
            record = self._read_record()
        except OSError:
            return {}
        if record is None or record is _CORRUPT:
            return {}
        return dict(record.get("state", {}))

    def current_holder(self):
        """当前记录里的持有者名字；没有或读不出时返回 None。"""
        try:
            record = self._read_record()
        except OSError:
            return None
        if record is None or record is _CORRUPT:
            return None
        return record.get("holder")

    def start(self):
        """启动后台续租线程，每 renew_interval 续一次，不占业务写入路径。"""
        with self._mu:
            if self._thread is not None:
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._renew_loop, name="lease-renew-%s" % self._node_id,
                daemon=True)
            self._thread.start()

    def stop(self):
        """停掉后台续租线程；停租不等于让位，租约会自然到期。"""
        with self._mu:
            thread, self._thread = self._thread, None
            self._stop.set()
        if thread is not None:
            thread.join()

    def close(self):
        self.release()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()

    def _renew_loop(self):
        while not self._stop.wait(self._renew_interval):
            self.renew()

    def _forfeit(self):
        self._token = None
        self._seq = 0
        self._last_renew_ok = None
        self._observed = None
        self._state = {}

    def _still_mine(self, record):
        return (record is not None and record is not _CORRUPT
                and record.get("holder") == self._node_id
                and record.get("token") == self._token)

    @staticmethod
    def _key(record):
        """记录指纹：holder/token/seq 任一变化都算记录动过。"""
        if record is None:
            return None
        if record is _CORRUPT:
            return _CORRUPT
        return (record.get("holder"), record.get("token"), record.get("seq"))

    def _read_record(self):
        """在共享锁下读记录，避免读到别人写了一半的内容。"""
        fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            try:
                return self._parse(os.read(fd, 65536))
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    @staticmethod
    def _parse(data):
        if not data:
            return None
        try:
            return json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return _CORRUPT

    def _fenced_update(self, check, holder, token, seq, state):
        """对租约记录做 读-校验-写 的原子更新（flock 保护临界区）。

        check(当前记录) 为假时返回 "conflict"，什么都不写。
        """
        fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                current = self._parse(os.read(fd, 65536))
                if not check(current):
                    return "conflict"
                payload = json.dumps({
                    "holder": holder,
                    "token": token,
                    "seq": seq,
                    "expires_at": self._wall_clock() + self._lease_duration,
                    "state": state,
                }, sort_keys=True).encode("utf-8")
                os.lseek(fd, 0, os.SEEK_SET)
                os.ftruncate(fd, 0)
                os.write(fd, payload)
                os.fsync(fd)
                return "ok"
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


class FencedStore:
    """带 fencing 检查的 KV 存储：拒绝 token 不大于已见最大值的写入。

    旧主拿着过期 token 的写入（比如 GC 停顿醒来后补写）在这里被挡住，
    这是防双主的最后一道防线。
    """

    def __init__(self):
        self._max_token = 0
        self._data = {}

    def write(self, key, value, token):
        if token is None or token <= self._max_token:
            raise StaleFencingTokenError(
                "token %r 已过期（已见最大 %d）" % (token, self._max_token))
        self._max_token = token
        self._data[key] = value

    def read(self, key, default=None):
        return self._data.get(key, default)
