"""coordx: 按顺序驱动一批参与者事务的协调者。

Coordinator 是单阶段的、严格按注册顺序串行推进：begin() 依次让每个
参与者开启本地事务，commit() 再依次让它们提交。参与者是注入进来的
对象，只能靠 begin()/commit() 沟通；一步抛错就原样往上抛，协调者
不留任何自己的状态，也不做补偿。

时间来源同样可注入（clock），默认取 time.monotonic，测试里可以换成
假时钟。协调者只在 begin() 时读一次时钟，用来算事务已经跑了多久。

TwoPhaseCoordinator 在同一套注入风格上提供两阶段提交：prepare 阶段
逐个征询参与者，全票赞成才落定 commit 决议，有人反对、超时或抛错就
落定 abort 决议并向已 prepare 的参与者 rollback。阶段边界的意图与
决议都通过注入的 TransactionStore 落盘；进程重启后拿同一 store、同一
批参与者调 recover() 即可推完未完成的决议。已落盘的决议永远不翻转。
"""

import copy
import json
import os
import tempfile
import time
import uuid


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


class PrepareParticipant(Participant):
    """两阶段参与者基类：在 begin/commit 之外再实现 prepare/rollback。

    老参与者只实现 begin()/commit() 也能继续给 Coordinator 用；只有
    TwoPhaseCoordinator 才要求参与者实现这里的两个方法。
    """

    def prepare(self):
        """征询能否提交：真值表示赞成，假值表示反对。

        返回真值后到收到 commit()/rollback() 之前，参与者必须把本地
        事务维持在“已准备、可提交也可撤销”的状态。实现也可以通过
        把注入时钟往前推触发协调者侧的超时，或者直接抛错。
        """
        raise NotImplementedError

    def rollback(self):
        """撤销一次已 prepare（或 prepare 超时）的本地事务。"""
        raise NotImplementedError


class TwoPhaseLedger(PrepareParticipant):
    """支持两阶段提交的内存账本。

    begin 之后写入先暂存；prepare 赞成后进入 prepared，此后只有
    commit() 会发布暂存值，rollback() 丢弃它并关闭事务。commit()/
    rollback() 对已结束的事务幂等，恢复重放不会重复生效。
    """

    def __init__(self, name, value=0, vote=True):
        super().__init__(name)
        self.value = value
        self._vote = vote
        self._pending = None
        self._open = False
        self._prepared = False

    def begin(self):
        self._open = True
        self._prepared = False
        self._pending = None

    def write(self, value):
        if not self._open or self._prepared:
            raise RuntimeError("%s: write outside open transaction" % self.name)
        self._pending = value

    def prepare(self):
        if not self._open:
            raise RuntimeError("%s: prepare without begin" % self.name)
        if self._vote:
            self._prepared = True
        return bool(self._vote)

    def commit(self):
        if not self._open and not self._prepared:
            raise RuntimeError("%s: commit without begin" % self.name)
        if self._prepared and self._pending is not None:
            self.value = self._pending
        self._pending = None
        self._prepared = False
        self._open = False

    def rollback(self):
        if not self._open:
            raise RuntimeError("%s: rollback without begin" % self.name)
        self._pending = None
        self._prepared = False
        self._open = False

    def phase(self):
        """当前本地阶段，方便演示与观察：open/prepared/closed。"""
        if not self._open:
            return "closed"
        return "prepared" if self._prepared else "open"


class TransactionStore(object):
    """事务意图与决议的落盘存储接口。

    记录按事务 id 保存一个字典，字段包括 state、decision（committing/
    aborting/None）、abort_reason、participants、prepared（已赞成或
    超时、等待裁决的参与者名字）、done（已收到裁决并完成的名字）。
    """

    def load(self, txid):
        """取一条事务记录；不存在返回 None。"""
        raise NotImplementedError

    def save(self, record):
        """整条写入（upsert）一条事务记录。"""
        raise NotImplementedError

    def pending(self):
        """返回所有未到终态（committed/aborted）的记录。"""
        raise NotImplementedError


class MemoryStore(TransactionStore):
    """进程内存储，测试用：写入即深拷贝，读出也是独立副本。"""

    def __init__(self):
        self._records = {}

    def load(self, txid):
        record = self._records.get(txid)
        return copy.deepcopy(record) if record is not None else None

    def save(self, record):
        self._records[record["id"]] = copy.deepcopy(record)

    def pending(self):
        return [
            copy.deepcopy(record)
            for record in self._records.values()
            if record["state"] not in ("committed", "aborted")
        ]


class JsonFileStore(TransactionStore):
    """JSON 文件存储：每次 save 都经临时文件原子替换整份文件。"""

    def __init__(self, path):
        self._path = path

    def _read(self):
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            return {}

    def load(self, txid):
        return copy.deepcopy(self._read().get(txid))

    def save(self, record):
        records = self._read()
        records[record["id"]] = record
        directory = os.path.dirname(os.path.abspath(self._path))
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tx-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(records, handle, ensure_ascii=False, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self._path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def pending(self):
        return [
            copy.deepcopy(record)
            for record in self._read().values()
            if record["state"] not in ("committed", "aborted")
        ]


class TwoPhaseCoordinator(object):
    """两阶段提交协调者。

    participants: 参与者序列，每个参与者实现 begin/prepare/commit/
        rollback（见 PrepareParticipant）。
    store: 意图与决议的落盘存储（TransactionStore）。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic。prepare
        期间参与者若把注入时钟往前推，前后读数之差达到 prepare_timeout
        即按超时（拒绝）处理。
    prepare_timeout: 单个参与者 prepare 的超时秒数。
    """

    def __init__(self, participants, store, clock=time.monotonic,
                 prepare_timeout=5.0):
        self._participants = list(participants)
        self._by_name = {p.name: p for p in self._participants}
        self._store = store
        self._clock = clock
        self._prepare_timeout = prepare_timeout
        self._active = False
        self._record = None
        self._last_abort_reason = None
        self._last_abort_detail = None

    def participants(self):
        """按注册顺序返回参与者名字组成的元组。"""
        return tuple(p.name for p in self._participants)

    def begin(self):
        """依次在各参与者上开启本地事务。"""
        if self._active:
            raise RuntimeError("coordinator already has an active transaction")
        for participant in self._participants:
            participant.begin()
        self._active = True

    def active(self):
        """当前是否有进行中的事务。"""
        return self._active

    def _persist(self):
        self._store.save(self._record)

    def _set_decision(self, decision, reason=None):
        """落定决议；记录里已有决议时永远不许翻转。"""
        if self._record["decision"] is not None:
            return
        self._record["decision"] = decision
        if reason is not None:
            self._record["abort_reason"] = reason
        self._persist()

    def prepare(self, txid=None):
        """第一阶段：先落意图，再按注册顺序逐个征询。

        任一参与者反对、抛错或超时，立即落定 abort 决议并向所有已
        prepare（含超时）者 rollback，决议记录写明原因（veto/error/
        timeout）。全部赞同时决议落为 committing，等待 commit。返回
        落定的决议字符串："committing" 或 "aborting"。
        """
        if not self._active:
            raise RuntimeError("no active transaction to prepare")
        if self._record is not None:
            raise RuntimeError("transaction already prepared")
        self._record = {
            "id": txid or uuid.uuid4().hex,
            "state": "preparing",
            "decision": None,
            "abort_reason": None,
            "abort_detail": None,
            "participants": [p.name for p in self._participants],
            "prepared": [],
            "asking": None,
            "done": [],
        }
        self._persist()

        for participant in self._participants:
            self._record["asking"] = participant.name
            self._persist()
            start = self._clock()
            try:
                vote = participant.prepare()
            except Exception as exc:
                self._record["asking"] = None
                self._persist()
                self._abort(
                    "error",
                    "%s: %s: %s" % (participant.name, type(exc).__name__, exc),
                    timed_out=False,
                )
                return "aborting"
            elapsed = self._clock() - start
            if elapsed > self._prepare_timeout:
                self._abort(
                    "timeout",
                    "%s: prepare timed out after %.3fs" % (participant.name, elapsed),
                    timed_out=True,
                )
                return "aborting"
            if not vote:
                self._record["asking"] = None
                self._persist()
                self._abort("veto", "%s: voted no" % participant.name,
                            timed_out=False)
                return "aborting"
            self._record["prepared"].append(participant.name)
            self._record["asking"] = None
            self._persist()

        self._set_decision("committing")
        return "committing"

    def _abort(self, reason, detail, timed_out):
        """落定 abort 决议，再按相反顺序 rollback 已准备者。

        超时的参与者没等到自己的 prepare 返回，但它的本地事务已经
        打开，同样要收到 rollback 结论。
        """
        pending = list(self._record["prepared"])
        if timed_out:
            pending.append(self._record["asking"])
        self._record["prepared"] = pending
        self._last_abort_reason = reason
        self._last_abort_detail = detail
        self._set_decision("aborting", reason)
        self._record["abort_detail"] = detail
        self._persist()
        self._finish_abort(pending)

    def _finish_abort(self, targets):
        done = set(self._record["done"])
        for name in reversed(targets):
            if name in done:
                continue
            self._by_name[name].rollback()
            done.add(name)
            self._record["done"] = sorted(done)
            self._persist()
        self._record["state"] = "aborted"
        self._persist()
        self._active = False
        self._record = None

    def _finish_commit(self, targets):
        done = set(self._record["done"])
        for name in targets:
            if name in done:
                continue
            self._by_name[name].commit()
            done.add(name)
            self._record["done"] = sorted(done)
            self._persist()
        self._record["state"] = "committed"
        self._persist()
        self._active = False
        self._record = None

    def commit(self):
        """第二阶段：要求 prepare 全票赞成时调用。

        先落定 commit 决议，再按注册顺序向已 prepare 者 commit。决议
        落盘后参与者抛错会原样上抛，事务保持未完成，recover() 可重放。
        prepare 已落定 abort 时原样抛错，已落盘的结论不翻转。
        """
        if not self._active or self._record is None:
            raise RuntimeError("no prepared transaction to commit")
        if self._record["decision"] == "aborting":
            raise RuntimeError("transaction aborted: %s"
                               % self._record.get("abort_reason"))
        self._set_decision("committing")
        self._finish_commit(list(self._record["prepared"]))

    def rollback(self):
        """主动放弃一次已 prepare 的事务（落定 abort 并补偿）。"""
        if not self._active or self._record is None:
            raise RuntimeError("no prepared transaction to roll back")
        if self._record["decision"] == "committing":
            raise RuntimeError("decision already committed")
        self._set_decision("aborting", "client")
        self._last_abort_reason = "client"
        self._finish_abort(list(self._record["prepared"]))

    def abort_reason(self):
        """最近一次事务被放弃的原因（veto/error/timeout/client）。"""
        return self._last_abort_reason

    def abort_detail(self):
        """最近一次放弃原因的可读细节（参与者与秒数等）。"""
        return self._last_abort_detail

    def recover(self, txid=None):
        """用同一 store、同一批参与者推完未完成决议。

        prepare 已开始但尚未落定决议的事务按 abort 推完（崩溃发生在
        决议前，不存在提交可能）；已落盘的 commit/abort 决议原样重放
        给还没收到结论的已 prepare 参与者，绝不翻转。返回本次推完的
        [(txid, outcome), ...]，outcome 为 "committed"/"aborted"。
        """
        if txid is not None:
            record = self._store.load(txid)
            records = [] if record is None else [record]
        else:
            records = self._store.pending()

        finished = []
        for record in sorted(records, key=lambda item: item["id"]):
            missing = [
                name for name in record["participants"]
                if name not in self._by_name
            ]
            if missing:
                raise RuntimeError("recover missing participants: %s"
                                   % ", ".join(missing))
            outcome = self._recover_record(record)
            finished.append((record["id"], outcome))
        return finished

    def _recover_record(self, record):
        self._record = record
        self._active = True
        try:
            if record["decision"] is None:
                self._set_decision("aborting", "recovery")
                self._record["abort_detail"] = (
                    "no decision on record before recovery")
                self._persist()
                self._last_abort_reason = "recovery"
                self._last_abort_detail = record.get("abort_detail")
                targets = list(record["prepared"])
                asking = record.get("asking")
                if asking and asking not in targets:
                    targets.append(asking)
                self._record["prepared"] = targets
                self._persist()
                self._finish_abort(targets)
                return "aborted"
            if record["decision"] == "committing":
                self._finish_commit(list(record["prepared"]))
                return "committed"
            self._finish_abort(list(record["prepared"]))
            return "aborted"
        finally:
            self._record = None
            self._active = False
