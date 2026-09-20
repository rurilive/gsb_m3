"""两阶段提交协调者（prepare / decision / recover）。

和 coordinator.py 里的单阶段 Coordinator 并存：单阶段行为一个字
不动，老参与者只要 begin()/commit() 也照旧能用。两阶段参与者在此
基础上多实现 prepare()/rollback() 即可（TwoPhaseParticipant 给出
了约定，内存账本的两阶段版本见 TwoPhaseLedger）。

决策口径（永远不许翻案）：

- 决议（commit / abort）在发给任何参与者之前先 append 进 store，
  之后无论进程是否被杀，recover 都只按这条记录走。
- prepare 之后、决议落盘之前被杀，记录里还没有决议：按 abort 推，
  即"不确定就作废"，已 prepare 的参与者一定收到 rollback。
- 每个参与者的 commit/rollback 完成后也写一条记录，恢复时不重复
  投递；已落盘的结论不会因为再来一次 recover 而改变。

超时时钟口径：

- clock 是注入的。prepare() 每问一个参与者读两次时钟（调用前、
  调用后），按两次读数之差认定该参与者是否超时，差值 >= timeout
  即超时。参与者可以在 prepare 里把时钟往前拨来模拟耗时。
- 超时按拒绝处理（整体 abort），但记录原因写 "timeout" 而不是
  "no"（参与者主动反对）或 "error"（prepare 抛错）。
"""

import json
import os
import time

YES = "yes"
NO = "no"
TIMEOUT = "timeout"
ERROR = "error"

COMMIT = "commit"
ABORT = "abort"


class Store:
    """意图日志的存储约定。append 追加一条记录，records 按落盘顺序读出。"""

    def append(self, record):
        raise NotImplementedError

    def records(self):
        raise NotImplementedError


class MemoryStore(Store):
    """进程内存储，演示和测试用；重启场景请用 FileStore。"""

    def __init__(self):
        self._records = []

    def append(self, record):
        self._records.append(dict(record))

    def records(self):
        return [dict(r) for r in self._records]


class FileStore(Store):
    """单事务意图日志，每行一条 JSON，append 即 flush+fsync 落盘。"""

    def __init__(self, path):
        self._path = path
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)

    def append(self, record):
        line = json.dumps(record, ensure_ascii=False)
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def records(self):
        if not os.path.exists(self._path):
            return []
        with open(self._path, "r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]


class TwoPhaseParticipant:
    """两阶段参与者约定：在 begin/commit 之外再实现 prepare/rollback。

    名字属性仍是 name。实际注入对象不必继承本类，只要四个方法齐备，
    协调者按方法是否存在来辨认，老参与者不会被逼着补新方法。
    """

    def __init__(self, name):
        self.name = name

    def begin(self):
        raise NotImplementedError

    def prepare(self):
        """征询能否提交。返回真值表示同意；也可以直接抛错表示反对。"""
        raise NotImplementedError

    def rollback(self):
        """作废本地事务。"""
        raise NotImplementedError

    def commit(self):
        """收到最终 commit 决议后落定。"""
        raise NotImplementedError


class TwoPhaseLedger(TwoPhaseParticipant):
    """支持两阶段的内存账本：prepare 锁值，commit 落定，rollback 作废。"""

    def __init__(self, name, value=0, prepare_delay=0.0):
        self.name = name
        self.value = value
        self._pending = None
        self._open = False
        self._prepared = False
        self._prepare_delay = prepare_delay

    def begin(self):
        self._open = True
        self._pending = None
        self._prepared = False

    def write(self, value):
        if not self._open:
            raise RuntimeError("%s: write outside transaction" % self.name)
        self._pending = value

    def prepare(self):
        if not self._open:
            raise RuntimeError("%s: prepare without begin" % self.name)
        if self._prepare_delay:
            time.sleep(self._prepare_delay)
        self._prepared = True
        return True

    def rollback(self):
        self._pending = None
        self._prepared = False
        self._open = False

    def commit(self):
        if not self._open:
            raise RuntimeError("%s: commit without begin" % self.name)
        if self._pending is not None:
            self.value = self._pending
        self._pending = None
        self._prepared = False
        self._open = False


class TwoPhaseCoordinator:
    """两阶段提交协调者。

    participants: 参与者序列，必须各自实现 begin/prepare/commit/rollback，
        name 不能重复；恢复时要用同一批（同名、同序）参与者。
    store: Store 实例，意图与决议都 append 进去，重启后原样拿回。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic；只用于
        prepare 前后读数之差来认定超时。
    timeout: prepare 允许的时钟读数差，默认 5 秒。
    """

    def __init__(self, participants, store, clock=time.monotonic, timeout=5.0):
        self._participants = list(participants)
        names = [p.name for p in self._participants]
        if len(set(names)) != len(names):
            raise ValueError("participant names must be unique: %r" % (names,))
        for p in self._participants:
            missing = [
                method
                for method in ("begin", "prepare", "commit", "rollback")
                if not callable(getattr(p, method, None))
            ]
            if missing:
                raise TypeError(
                    "%s is not two-phase capable, missing: %s"
                    % (p.name, ", ".join(missing))
                )
        self._by_name = dict(zip(names, self._participants))
        self._store = store
        self._clock = clock
        self._timeout = float(timeout)

        existing = self._store.records()
        begin_records = [r for r in existing if r.get("event") == "begin"]
        if len(begin_records) > 1:
            raise RuntimeError("store contains more than one transaction")
        if begin_records:
            record = begin_records[0]
            if tuple(record.get("participants", ())) != tuple(names):
                raise RuntimeError(
                    "participants do not match the transaction in the store"
                )
        # 无论 store 里有没有未完成的事务，构造出来都先处于休眠：
        # 新事务走 begin()，推完旧决议走 recover()。
        self._active = False

    def participants(self):
        """按注册顺序返回参与者名字组成的元组。"""
        return tuple(p.name for p in self._participants)

    def active(self):
        """是否存在尚未推完决议的事务。"""
        return self._active

    def begin(self):
        """登记事务意图并依次让参与者开启本地事务。"""
        if self._store.records():
            raise RuntimeError("store is not empty; call recover() instead")
        if self._active:
            raise RuntimeError("coordinator already has an active transaction")
        self._store.append(
            {"event": "begin", "participants": list(self.participants())}
        )
        begun = []
        try:
            for p in self._participants:
                p.begin()
                begun.append(p)
        except Exception:
            self._write_decision(ABORT, "begin-failed")
            for p in reversed(begun):
                p.rollback()
                self._store.append(
                    {"event": "delivered", "participant": p.name, "action": "rollback"}
                )
            self._mark_finished(ABORT)
            raise
        self._active = True

    def prepare(self):
        """阶段一：逐个征询。返回 {名字: 结论}，出现反对即停止后续征询。"""
        if not self._active:
            raise RuntimeError("no active transaction to prepare")
        if self._decision_record() is not None:
            raise RuntimeError("decision already recorded")
        votes = {}
        for p in self._participants:
            start = self._clock()
            try:
                answer = p.prepare()
            except Exception as exc:
                self._store.append(
                    {
                        "event": "vote",
                        "participant": p.name,
                        "vote": ERROR,
                        "detail": str(exc),
                    }
                )
                votes[p.name] = ERROR
                return votes
            end = self._clock()
            if end - start >= self._timeout:
                vote = TIMEOUT
            elif not answer:
                vote = NO
            else:
                vote = YES
            self._store.append(
                {"event": "vote", "participant": p.name, "vote": vote}
            )
            votes[p.name] = vote
            if vote != YES:
                return votes
        return votes

    def decide(self, outcome=None):
        """落定决议并先写盘；不传 outcome 时按投票结果自动判定。

        已有落盘决议时原样返回，绝不改判。
        """
        record = self._decision_record()
        if record is not None:
            return record["outcome"]
        if not self._active:
            raise RuntimeError("no active transaction to decide")

        votes = self.votes()
        if outcome is None:
            outcome = (
                COMMIT
                if len(votes) == len(self._participants)
                and all(vote == YES for vote in votes.values())
                else ABORT
            )
        return self._write_decision(outcome)

    def resolve(self, outcome=None):
        """落定决议并把结论投递给所有参与者（阶段二）。"""
        if not self._active:
            raise RuntimeError("no active transaction to resolve")
        outcome = self.decide(outcome)
        self._deliver(outcome)
        self._mark_finished(outcome)
        self._active = False
        return outcome

    def recover(self):
        """用同一 store、同一批参与者推完未完成的决议，返回最终结局。

        已落盘的结论永远照走；prepare 过但没有决议记录的，按 abort
        推（不确定就作废）。已经投递过的参与者不重复投递。
        """
        records = self._store.records()
        if not any(r.get("event") == "begin" for r in records):
            raise RuntimeError("nothing to recover in the store")

        decision = self._decision_record(records)
        outcome = (
            decision["outcome"]
            if decision is not None
            else self._write_decision(ABORT)
        )
        self._deliver(outcome)
        self._mark_finished(outcome)
        return outcome

    def run(self):
        """一条路走完：begin -> prepare -> 决议 -> 投递，返回结局。"""
        self.begin()
        self.prepare()
        return self.resolve()

    def votes(self):
        """返回落盘的征询结论 {名字: yes/no/timeout/error}。"""
        return {
            r["participant"]: r["vote"]
            for r in self._store.records()
            if r.get("event") == "vote"
        }

    def decision(self):
        """已落盘的最终结局（commit/abort），未落盘时为 None。"""
        record = self._decision_record()
        return record["outcome"] if record is not None else None

    def reasons(self):
        """abort 的文字原因（如 p2=timeout）；commit 或未决议时为 None。"""
        record = self._decision_record()
        if record is None or record["outcome"] != ABORT:
            return None
        return record.get("reason")

    def _decision_record(self, records=None):
        if records is None:
            records = self._store.records()
        decisions = [r for r in records if r.get("event") == "decision"]
        return decisions[0] if decisions else None

    def _write_decision(self, outcome, reason=None):
        """把决议 append 进 store；调用方必须保证此前没有决议记录。"""
        record = {"event": "decision", "outcome": outcome}
        if outcome == ABORT:
            reasons = [
                "%s=%s" % (name, vote)
                for name, vote in self.votes().items()
                if vote != YES
            ]
            record["reason"] = reason if reason is not None else ";".join(reasons)
        self._store.append(record)
        return outcome

    def _deliver(self, outcome):
        records = self._store.records()
        completed = {
            r.get("participant")
            for r in records
            if r.get("event") == "delivered"
        }
        if outcome == COMMIT:
            order = self._participants
            action = "commit"
        else:
            asked = [
                self._by_name[r["participant"]]
                for r in records
                if r.get("event") == "vote"
            ]
            order = reversed(asked)
            action = "rollback"
        for p in order:
            if p.name in completed:
                continue
            getattr(p, action)()
            self._store.append(
                {"event": "delivered", "participant": p.name, "action": action}
            )

    def _mark_finished(self, outcome):
        records = self._store.records()
        if not any(r.get("event") == "done" for r in records):
            self._store.append({"event": "done", "outcome": outcome})
