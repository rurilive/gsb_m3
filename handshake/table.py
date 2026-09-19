"""转移表：状态机行为的唯一来源。

表按 (当前状态, 事件) 组织，同一组合可以有多行（用守卫区分）；
Session 按书写顺序取第一条全部守卫通过的行执行，没有任何行生效
视为协议违规，抛 ProtocolError。

Row 字段：
- next    目标状态
- guards  守卫元组，签名 (payload, session) -> bool
- actions 动作元组，签名 (session, payload)，状态变更后按序执行
- sends   发出的对端消息名元组，进 outbox 并写日志
- timer   进入目标状态后武装的定时器秒数；None 表示该状态无定时器
- target  可选动态目标，签名 (payload, session) -> State；给定时
           覆盖 next（用于「回进入前稳态」这类运行时决定的转移）
"""

from collections import namedtuple

from .states import REKEY_TIMEOUT, SUITES, Ev, State, T_AUTH, T_HELLO, T_KEY

Row = namedtuple(
    "Row", "state event next guards actions sends timer target",
    defaults=(None, (), (), (), None, None),
)


def suite_known(payload, session):
    """守卫：对端报的套件是已知的。"""
    return payload in SUITES


def suite_is_strong(payload, session):
    return session.suite == "strong"


def suite_is_weak(payload, session):
    return session.suite == "weak"


def store_suite(session, payload):
    """动作：记下本会话协商出的套件。"""
    session.suite = payload


def remember_rekey_resume_full(session, payload):
    """动作：记住 rekey 成功/失败后要回到的稳态。"""
    session.rekey_resume = State.FULL


def remember_rekey_resume_degraded(session, payload):
    session.rekey_resume = State.DEGRADED


def resume_from_rekey(payload, session):
    """动态目标：回 rekey 进入前记住的稳态。"""
    return session.rekey_resume


TABLE = [
    # 握手推进
    Row(State.CLOSED, Ev.START, State.HELLO_SENT, sends=("c_hello",),
        timer=T_HELLO),
    Row(State.HELLO_SENT, Ev.PEER_HELLO, State.KEY_SENT,
        guards=(suite_known,), actions=(store_suite,), sends=("c_key",),
        timer=T_KEY),
    Row(State.KEY_SENT, Ev.PEER_KEY, State.AUTH_SENT, sends=("c_auth",),
        timer=T_AUTH),
    # 认证结果按套件分流到两个稳态
    Row(State.AUTH_SENT, Ev.PEER_AUTH_OK, State.FULL,
        guards=(suite_is_strong,)),
    Row(State.AUTH_SENT, Ev.PEER_AUTH_OK, State.DEGRADED,
        guards=(suite_is_weak,)),
    Row(State.AUTH_SENT, Ev.PEER_AUTH_FAIL, State.CLOSED,
        sends=("c_close",)),
    # 各阶段超时：整体放弃，回 CLOSED
    Row(State.HELLO_SENT, Ev.TIMEOUT, State.CLOSED),
    Row(State.KEY_SENT, Ev.TIMEOUT, State.CLOSED),
    Row(State.AUTH_SENT, Ev.TIMEOUT, State.CLOSED),
    # 稳态下对端要求关闭
    Row(State.FULL, Ev.PEER_CLOSE, State.CLOSED, sends=("c_close",)),
    Row(State.DEGRADED, Ev.PEER_CLOSE, State.CLOSED, sends=("c_close",)),
    # rekey 子流程：任一稳态可触发，记住进入前的稳态
    Row(State.FULL, Ev.REKEY, State.REKEY_OFFER_SENT,
        actions=(remember_rekey_resume_full,),
        sends=("c_rekey_offer",), timer=REKEY_TIMEOUT),
    Row(State.DEGRADED, Ev.REKEY, State.REKEY_OFFER_SENT,
        actions=(remember_rekey_resume_degraded,),
        sends=("c_rekey_offer",), timer=REKEY_TIMEOUT),
    # 三步：offer -> accept -> confirm -> done，每步重新武装定时器
    Row(State.REKEY_OFFER_SENT, Ev.PEER_REKEY_ACCEPT,
        State.REKEY_CONFIRM_SENT,
        sends=("c_rekey_confirm",), timer=REKEY_TIMEOUT),
    # 成功：动态回进入前的稳态，连接不断、无定时器
    Row(State.REKEY_CONFIRM_SENT, Ev.PEER_REKEY_DONE, None,
        target=resume_from_rekey),
    # 任一步超时：弃新密钥，动态回原稳态
    Row(State.REKEY_OFFER_SENT, Ev.TIMEOUT, None,
        target=resume_from_rekey),
    Row(State.REKEY_CONFIRM_SENT, Ev.TIMEOUT, None,
        target=resume_from_rekey),
]
