"""unregister 与错误隔离的行为测试。"""

import unittest

from pluginhost import Plugin, PluginHost
from pluginhost.host import Diagnostic


class Rec(Plugin):
    """记录收到的 payload，不改写。"""

    def __init__(self, name, priority, log):
        self.name = name
        self.priority = priority
        self.log = log

    def on_message(self, message):
        self.log.append((self.name, message))
        return None


class Appender(Plugin):
    """给消息加后缀，用于验证链式传递。"""

    def __init__(self, name, priority, suffix):
        self.name = name
        self.priority = priority
        self.suffix = suffix

    def on_message(self, message):
        return message + self.suffix


class Boom(Plugin):
    """on_message 固定抛错的插件。"""

    def __init__(self, name, priority, exc=None):
        self.name = name
        self.priority = priority
        self.exc = exc if exc is not None else RuntimeError("boom")

    def on_message(self, message):
        raise self.exc


class ErrorWatcher(Plugin):
    """记录 on_error 回调收到的 Diagnostic。"""

    def __init__(self, name, priority, log):
        self.name = name
        self.priority = priority
        self.log = log

    def on_error(self, diag):
        self.log.append((self.name, diag))


class TestUnregister(unittest.TestCase):
    def test_unregister_removes_from_chain(self):
        host = PluginHost()
        log = []
        rec = Rec("rec", 0, log)
        app = Appender("app", 10, "+app")
        host.register(rec)
        host.register(app)
        host.unregister(rec)
        self.assertEqual(host.plugins, [app])
        self.assertNotIn(rec, host)
        self.assertEqual(len(host), 1)
        with self.assertRaises(KeyError):
            host.plugin("rec")
        out = host.dispatch("on_message", "x")
        self.assertEqual(out, "x+app")
        self.assertEqual(log, [])  # 注销后钩子不再被调用

    def test_unregister_is_idempotent(self):
        host = PluginHost()
        app = Appender("app", 10, "+app")
        host.register(app)
        host.unregister(Appender("ghost", 0, "+g"))  # 从未注册，静默
        host.unregister(app)
        host.unregister(app)  # 重复注销，静默
        self.assertEqual(host.plugins, [])

    def test_unregister_makes_no_callbacks(self):
        host = PluginHost()
        log = []
        watcher = ErrorWatcher("watcher", 0, log)
        host.register(watcher)
        host.unregister(watcher)
        self.assertEqual(log, [])  # 注销不触发任何回调
        self.assertEqual(host.diagnostics, [])

    def test_reregister_goes_to_end_of_priority_group(self):
        host = PluginHost()
        a = Appender("a", 10, "+a")
        b = Appender("b", 10, "+b")
        c = Appender("c", 10, "+c")
        for p in (a, b, c):
            host.register(p)
        host.unregister(a)
        host.register(a)  # 重新注册：排到同 priority 末尾，不回到原位
        self.assertEqual([p.name for p in host.plugins], ["b", "c", "a"])
        self.assertEqual(host.dispatch("on_message", "x"), "x+b+c+a")

    def test_unregister_during_dispatch_takes_effect_next_round(self):
        host = PluginHost()
        log = []
        rec = Rec("rec", 10, log)

        class Unregisterer(Plugin):
            name = "unreg"
            priority = 0

            def on_message(self, message):
                host.unregister(rec)  # dispatch 途中注销后面的插件
                return None

        host.register(Unregisterer())
        host.register(rec)
        host.dispatch("on_message", "x")
        # 本轮用开始时的快照：rec 仍被调用
        self.assertEqual(log, [("rec", "x")])
        self.assertEqual(host.plugins, [host.plugin("unreg")])
        host.dispatch("on_message", "y")
        # 下一轮 rec 已不在链上
        self.assertEqual(log, [("rec", "x")])

    def test_self_unregister_during_dispatch(self):
        host = PluginHost()
        log = []

        class Selfish(Plugin):
            name = "selfish"
            priority = 0

            def on_message(self, message):
                log.append(message)
                host.unregister(self)
                return None

        host.register(Selfish())
        host.dispatch("on_message", "x")
        host.dispatch("on_message", "y")
        self.assertEqual(log, ["x"])  # 第二轮起不再被调用
        self.assertEqual(len(host), 0)


class TestErrorIsolation(unittest.TestCase):
    def test_error_skips_only_offender(self):
        host = PluginHost()
        log = []
        host.register(Appender("app", 0, "+app"))
        host.register(Boom("boom", 5))
        host.register(Rec("rec", 10, log))
        out = host.dispatch("on_message", "x")
        # boom 抛错前的链上值继续传给下游，dispatch 正常返回
        self.assertEqual(log, [("rec", "x+app")])
        self.assertEqual(out, "x+app")

    def test_diagnostic_records_plugin_hook_and_error(self):
        host = PluginHost()
        exc = ValueError("bad payload")
        host.register(Boom("boom", 0, exc))
        host.dispatch("on_message", "x")
        self.assertEqual(len(host.diagnostics), 1)
        diag = host.diagnostics[0]
        self.assertIsInstance(diag, Diagnostic)
        self.assertEqual(diag.plugin, "boom")
        self.assertEqual(diag.hook, "on_message")
        self.assertIs(diag.error, exc)

    def test_multiple_errors_appended_in_order(self):
        host = PluginHost()
        host.register(Boom("b1", 0))
        host.register(Boom("b2", 10))
        host.dispatch("on_message", "x")
        host.dispatch("on_message", "y")
        self.assertEqual(
            [(d.plugin, d.hook) for d in host.diagnostics],
            [("b1", "on_message"), ("b2", "on_message"),
             ("b1", "on_message"), ("b2", "on_message")])

    def test_error_hook_name_reflects_dispatch_hook(self):
        host = PluginHost()

        class TickBoom(Plugin):
            name = "tick-boom"

            def on_tick(self, payload):
                raise KeyError("tick")

        host.register(TickBoom())
        host.dispatch("on_tick", None)
        self.assertEqual(host.diagnostics[0].hook, "on_tick")
        self.assertIsInstance(host.diagnostics[0].error, KeyError)

    def test_on_error_called_on_all_plugins_in_priority_order(self):
        host = PluginHost()
        log = []
        host.register(ErrorWatcher("w2", 20, log))
        host.register(Boom("boom", 10))
        host.register(ErrorWatcher("w1", 0, log))
        host.dispatch("on_message", "x")
        # 所有在册插件（含出错者自身，走基类默认实现）按 priority 顺序触发
        self.assertEqual([name for name, _ in log], ["w1", "w2"])
        for _, diag in log:
            self.assertEqual(diag.plugin, "boom")
            self.assertEqual(diag.hook, "on_message")

    def test_on_error_error_recorded_without_retrigger(self):
        host = PluginHost()
        log = []

        class BadWatcher(Plugin):
            name = "bad-watcher"
            priority = 0

            def on_error(self, diag):
                raise RuntimeError("watcher exploded")

        host.register(BadWatcher())
        host.register(ErrorWatcher("good-watcher", 10, log))
        host.register(Boom("boom", 20))
        host.dispatch("on_message", "x")
        # good-watcher 只被调一次：on_error 抛错不二次触发
        self.assertEqual([name for name, _ in log], ["good-watcher"])
        self.assertEqual(len(host.diagnostics), 2)
        self.assertEqual(host.diagnostics[0].plugin, "boom")
        self.assertEqual(host.diagnostics[0].hook, "on_message")
        self.assertEqual(host.diagnostics[1].plugin, "bad-watcher")
        self.assertEqual(host.diagnostics[1].hook, "on_error")
        self.assertIsInstance(host.diagnostics[1].error, RuntimeError)

    def test_register_unregister_inside_on_error_is_safe(self):
        host = PluginHost()
        log = []
        late = ErrorWatcher("late", 20, log)
        newcomer = ErrorWatcher("newcomer", 30, log)

        class Meddler(Plugin):
            name = "meddler"
            priority = 0
            done = False

            def on_error(self, diag):
                if not self.done:
                    host.unregister(late)      # 摘掉还没轮到的 watcher
                    host.register(newcomer)    # 事件途中注册新插件
                    self.done = True

        host.register(Meddler())
        host.register(Boom("boom", 10))
        host.register(late)
        host.dispatch("on_message", "x")
        # error 事件按开始时的快照遍历：late 仍收到本次 diag，
        # newcomer 本轮不参与；每个在册插件恰好一次，无重复无漏触发
        self.assertEqual([name for name, _ in log], ["late"])
        self.assertNotIn(late, host)
        self.assertIn(newcomer, host)
        # 下一轮：late 已摘除，newcomer 参与
        host.dispatch("on_message", "y")
        self.assertEqual([name for name, _ in log], ["late", "newcomer"])

    def test_dispatch_returns_payload_despite_errors(self):
        host = PluginHost()
        host.register(Boom("b1", 0))
        host.register(Appender("app", 5, "+app"))
        host.register(Boom("b2", 10))
        out = host.dispatch("on_message", "x")
        self.assertEqual(out, "x+app")
        self.assertEqual(len(host.diagnostics), 2)


if __name__ == "__main__":
    unittest.main()
