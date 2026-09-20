"""flagr 演示：编译规则 -> 按上下文求值 -> 决策与解释。"""

from flagr import compile_rules

RULES = """\
# 网关灰度规则
flag checkout-v2
when and(country in [CN, US], plan eq pro) -> on
default off

flag beta-ui
when or(vip eq true, age ge 18) -> on
default off

flag corp-rollout
when and(not(email regex "@corp\\.example\\.com$"), vip eq false) -> off
when email regex "@corp\\.example\\.com$" -> on
default off
"""

CONTEXTS = [
    ("cn-pro 请求", {"country": "CN", "plan": "pro", "vip": False,
                     "age": 17, "email": "li@corp.example.com"}),
    ("us-vip 请求", {"country": "US", "plan": "free", "vip": True,
                     "age": 30, "email": "joe@other.example.com"}),
    ("jp 新用户", {"country": "JP", "plan": "free", "vip": False,
                   "age": 9, "email": "hana@example.com"}),
]


def main():
    engine = compile_rules(RULES)
    for flag in engine.flags:
        print(f"=== {flag} ===")
        for label, ctx in CONTEXTS:
            decision = engine.evaluate(flag, ctx)
            print(decision.explain())
            print(f"  （{label}）\n")


if __name__ == "__main__":
    main()
