"""pluginhost 演示：注册三个插件跑 dispatch，再演示注销与错误隔离。"""

from pluginhost import Plugin, PluginHost
from pluginhost.plugins import AuditTrail, FooterSigner, KeywordMask


def build_host():
    host = PluginHost()
    audit = AuditTrail()
    host.register(audit)
    host.register(KeywordMask(["密码"]))
    host.register(FooterSigner(" -- 已签名"))
    return host, audit


def show(host, message):
    print("in : %r" % message)
    out = host.dispatch("on_message", message)
    print("out: %r" % out)
    print("链上插件:", [p.name for p in host.plugins])
    print()


def main():
    host, audit = build_host()

    print("=== 正常消息：沿链签名 ===")
    show(host, "今晚发版窗口 22:00")

    print("=== 命中关键词：被中间的合规插件遮蔽 ===")
    show(host, "我的密码是 123456")
    print("audit 见过的消息:", audit.seen)

    print("=== 注销 mask：不再遮蔽，链上也看不到它 ===")
    host.unregister(host.plugin("mask"))
    show(host, "我的密码是 123456")

    print("=== 错误隔离：抛错的插件被跳过，错误记入 diagnostics ===")

    class Bombshell(Plugin):
        name = "bomb"
        priority = 60

        def on_message(self, message):
            raise RuntimeError("bomb 炸了")

    host.register(Bombshell())
    show(host, "正常消息")
    print("diagnostics:", host.diagnostics)


if __name__ == "__main__":
    main()
