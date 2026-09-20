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
"""

CONTEXTS = [
    ("cn-pro 请求", {"country": "CN", "plan": "pro", "vip": False, "age": 17}),
    ("us-vip 请求", {"country": "US", "plan": "free", "vip": True, "age": 30}),
    ("jp 新用户", {"country": "JP", "plan": "free", "vip": False, "age": 9}),
]

# 正则圈人 + 条件取反：公司邮箱域、且非预发环境
REGEX_RULES = r"""
flag staff-beta
when and(email regex "@corp\.example\.com$", not(env eq staging)) -> on
default off
"""

REGEX_CONTEXTS = [
    ("员工邮箱+线上", {"email": "ops@corp.example.com", "env": "prod"}),
    ("员工邮箱+预发", {"email": "ops@corp.example.com", "env": "staging"}),
    ("外部邮箱", {"email": "user@gmail.com", "env": "prod"}),
]


def main():
    engine = compile_rules(RULES)
    for flag in engine.flags:
        print(f"=== {flag} ===")
        for label, ctx in CONTEXTS:
            decision = engine.evaluate(flag, ctx)
            print(decision.explain())
            print(f"  （{label}）\n")

    engine = compile_rules(REGEX_RULES)
    for flag in engine.flags:
        print(f"=== {flag} ===")
        for label, ctx in REGEX_CONTEXTS:
            decision = engine.evaluate(flag, ctx)
            print(decision.explain())
            print(f"  （{label}）\n")


if __name__ == "__main__":
    main()
