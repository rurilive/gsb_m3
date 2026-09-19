"""转移表：状态机行为的唯一来源。

表按 (当前状态, 事件) 组织，同一组合可以有多行（用守卫区分）；
Session 按书写顺序取第一条全部守卫通过的行执行，没有任何行生效
视为协议违规，抛 ProtocolError。

Row 字段：
- next    目标状态；目标需动态决定时（如回进入前的稳态）置 None，
          改用 next_fn
- next_fn 动态目标函数 (session) -> State，next 为 None 时生效
- guards  守卫元组，签名 (payload, session) -> bool
- actions 动作元组，签名 (session, payload)，状态变更后按序执行
- sends   发出的对端消息名元组，进 outbox 并写日志
- timer   进入目标状态后武装的定时器秒数；None 表示该状态无定时器
"""

from collections import namedtuple

from .states import REKEY_TIMEOUT, SUITES, Ev, State, T_AUTH, T_HELLO, T_KEY

Row = namedtuple(
    "Row", "state event next guards actions sends timer next_fn",
    defaults=((), (), (), None, None),
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


def remember_return(state):
    """动作工厂：记下 rekey 子流程结束后要回去的稳态。"""
    def action(session, payload):
        session.resume_state = state
    return action


def clear_return(session, payload):
    """动作：子流程结束，清掉返回点记录。"""
    session.resume_state = None


def resume_steady(session):
    """动态目标：回到进入 rekey 子流程前的稳态。"""
    return session.resume_state


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
    # rekey 子流程：任一稳态可触发，每步都武装 REKEY_TIMEOUT；
    # 成功或任一步超时都回到进入前的稳态（动态目标），连接不断
    Row(State.FULL, Ev.REKEY, State.REKEY_OFFER_SENT,
        actions=(remember_return(State.FULL),), sends=("c_rekey_offer",),
        timer=REKEY_TIMEOUT),
    Row(State.DEGRADED, Ev.REKEY, State.REKEY_OFFER_SENT,
        actions=(remember_return(State.DEGRADED),),
        sends=("c_rekey_offer",), timer=REKEY_TIMEOUT),
    Row(State.REKEY_OFFER_SENT, Ev.PEER_REKEY_ACCEPT,
        State.REKEY_CONFIRM_SENT, sends=("c_rekey_confirm",),
        timer=REKEY_TIMEOUT),
    Row(State.REKEY_CONFIRM_SENT, Ev.PEER_REKEY_DONE, None,
        actions=(clear_return,), next_fn=resume_steady),
    Row(State.REKEY_OFFER_SENT, Ev.TIMEOUT, None,
        actions=(clear_return,), next_fn=resume_steady),
    Row(State.REKEY_CONFIRM_SENT, Ev.TIMEOUT, None,
        actions=(clear_return,), next_fn=resume_steady),
]
