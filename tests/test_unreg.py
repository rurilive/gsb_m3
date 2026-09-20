"""unregister 与错误隔离的行为测试。"""

import unittest

from pluginhost import Diagnostic, Plugin, PluginHost


class Probe(Plugin):
    """可配置名字/优先级，记录 on_message 与 on_error 调用。"""

    def __init__(self, name, priority, log):
        self.name = name
        self.priority = priority
        self.log = log

    def on_message(self, message):
        self.log.append(("on_message", self.name, message))
        return None

    def on_error(self, diag):
        self.log.append(("on_error", self.name, diag))


class Boom(Plugin):
    """on_message 固定抛错的插件，可选记录 on_error 调用。"""

    def __init__(self, name, priority, exc=None, log=None):
        self.name = name
        self.priority = priority
        self.exc = exc or RuntimeError("boom")
        self.log = log

    def on_message(self, message):
        raise self.exc

    def on_error(self, diag):
        if self.log is not None:
            self.log.append(("on_error", self.name, diag))


class TestUnregister(unittest.TestCase):
    def test_unregister_removes_plugin_from_chain(self):
        host = PluginHost()
        log = []
        a = Probe("a", 0, log)
        b = Probe("b", 10, log)
        host.register(a)
        host.register(b)
        host.unregister(a)
        self.assertEqual(host.plugins, [b])
        self.assertNotIn(a, host)
        self.assertEqual(len(host), 1)
        host.dispatch("on_message", "x")
        self.assertEqual([t[1] for t in log], ["b"])

    def test_unregister_is_idempotent(self):
        host = PluginHost()
        a = Probe("a", 0, [])
        host.register(a)
        host.unregister(a)
        host.unregister(a)  # 已注销：静默返回
        host.unregister(Probe("ghost", 0, []))  # 从未注册：静默返回
        host.unregister(object())  # 非插件也不报错
        self.assertEqual(host.plugins, [])

    def test_unregister_triggers_no_callbacks(self):
        host = PluginHost()
        log = []
        a = Probe("a", 0, log)
        host.register(a)
        host.unregister(a)
        self.assertEqual(log, [])  # 只摘除，无额外回调
        self.assertEqual(host.diagnostics, [])

    def test_unregister_frees_name_for_reregister(self):
        host = PluginHost()
        host.register(Probe("a", 0, []))
        host.unregister(host.plugin("a"))
        host.register(Probe("a", 0, []))  # 注销后同名可再注册
        self.assertEqual([p.name for p in host.plugins], ["a"])

    def test_reregistered_plugin_goes_to_end(self):
        host = PluginHost()
        log = []
        a, b, c = (Probe(n, 10, log) for n in "abc")
        for p in (a, b, c):
            host.register(p)
        host.unregister(a)
        host.register(a)
        # 同 priority：重新注册排在末尾，而不是回到原位
        self.assertEqual([p.name for p in host.plugins], ["b", "c", "a"])


class TestRoundBoundary(unittest.TestCase):
    def test_unregister_during_dispatch_applies_next_round(self):
        host = PluginHost()
        log = []
        late = Probe("late", 20, log)

        class Unregisterer(Plugin):
            name = "unreg"
            priority = 0

            def __init__(self):
                self.done = False

            def on_message(self, message):
                if not self.done:
                    host.unregister(late)  # dispatch 途中注销后面的插件
                    self.done = True
                return None

        host.register(Unregisterer())
        host.register(late)
        host.dispatch("on_message", "x")
        # 本轮用的是开始时的快照：late 仍被调用
        self.assertEqual([t[1] for t in log], ["late"])
        host.dispatch("on_message", "y")
        # 下一轮起 late 不在链上
        self.assertEqual([t[1] for t in log], ["late"])

    def test_self_unregister_during_dispatch(self):
        host = PluginHost()
        log = []

        class SelfRemove(Plugin):
            name = "self-remove"
            priority = 0

            def on_message(self, message):
                log.append("called")
                host.unregister(self)
                return None

        host.register(SelfRemove())
        host.dispatch("on_message", "x")
        host.dispatch("on_message", "y")
        self.assertEqual(log, ["called"])
        self.assertEqual(host.plugins, [])


class TestErrorIsolation(unittest.TestCase):
    def test_error_skips_only_failing_plugin(self):
        host = PluginHost()
        log = []

        class Append(Plugin):
            def __init__(self, name, priority, suffix):
                self.name = name
                self.priority = priority
                self.suffix = suffix

            def on_message(self, message):
                log.append((self.name, message))
                return message + self.suffix

        host.register(Append("first", 0, "+a"))
        host.register(Boom("boom", 10))
        host.register(Append("last", 20, "+c"))
        out = host.dispatch("on_message", "x")
        # boom 抛错前的链上值继续往下游传，后面的插件照常调用
        self.assertEqual(out, "x+a+c")
        self.assertEqual(log, [("first", "x"), ("last", "x+a")])

    def test_diagnostics_recorded_in_occurrence_order(self):
        host = PluginHost()
        e1, e2 = RuntimeError("e1"), ValueError("e2")
        host.register(Boom("f1", 0, e1))
        host.register(Boom("f2", 10, e2))
        host.dispatch("on_message", "x")
        self.assertEqual(len(host.diagnostics), 2)
        first, second = host.diagnostics
        self.assertIsInstance(first, Diagnostic)
        self.assertEqual((first.plugin, first.hook), ("f1", "on_message"))
        self.assertIs(first.error, e1)
        self.assertEqual((second.plugin, second.hook), ("f2", "on_message"))
        self.assertIs(second.error, e2)

    def test_dispatch_keeps_working_after_error(self):
        host = PluginHost()
        host.register(Boom("boom", 0))
        host.dispatch("on_message", "x")
        out = host.dispatch("on_message", "y")
        self.assertEqual(out, "y")
        self.assertEqual(len(host.diagnostics), 2)


class TestErrorEvent(unittest.TestCase):
    def test_on_error_called_on_all_plugins_by_priority(self):
        host = PluginHost()
        log = []
        host.register(Probe("p-late", 90, log))
        host.register(Boom("boom", 50, log=log))
        host.register(Probe("p-early", 0, log))
        host.dispatch("on_message", "x")
        calls = [t for t in log if t[0] == "on_error"]
        # 按 priority 顺序，含抛错的插件自己
        self.assertEqual([t[1] for t in calls], ["p-early", "boom", "p-late"])
        # 每个插件收到的都是 diagnostics 里那一条
        self.assertEqual(len(host.diagnostics), 1)
        for call in calls:
            self.assertIs(call[2], host.diagnostics[0])
        diag = host.diagnostics[0]
        self.assertEqual((diag.plugin, diag.hook), ("boom", "on_message"))

    def test_on_error_error_only_recorded_not_retriggered(self):
        host = PluginHost()
        log = []
        err = RuntimeError("on_error boom")

        class BadHandler(Plugin):
            name = "bad-handler"
            priority = 0

            def __init__(self):
                self.calls = 0

            def on_error(self, diag):
                self.calls += 1
                raise err

        handler = BadHandler()
        host.register(handler)
        host.register(Probe("witness", 10, log))
        host.register(Boom("boom", 20))
        host.dispatch("on_message", "x")
        # 原始错误 + on_error 错误各一条，按发生顺序
        self.assertEqual(len(host.diagnostics), 2)
        second = host.diagnostics[1]
        self.assertEqual((second.plugin, second.hook), ("bad-handler", "on_error"))
        self.assertIs(second.error, err)
        # 不二次触发：bad-handler 的 on_error 只被调一次
        self.assertEqual(handler.calls, 1)
        # 其他插件的 on_error 照常调用
        calls = [t for t in log if t[0] == "on_error"]
        self.assertEqual([t[1] for t in calls], ["witness"])

    def test_on_error_may_register_and_unregister_safely(self):
        host = PluginHost()
        log = []

        class Handler(Plugin):
            def __init__(self, name, priority):
                self.name = name
                self.priority = priority

            def on_error(self, diag):
                log.append((self.name, diag.plugin))

        doomed = Handler("doomed", 10)
        late = Handler("late-handler", 20)

        class Manager(Plugin):
            name = "manager"
            priority = 0

            def __init__(self):
                self.done = False

            def on_error(self, diag):
                if not self.done:
                    self.done = True
                    host.unregister(doomed)
                    host.register(late)

        host.register(Manager())
        host.register(doomed)
        host.register(Boom("boom", 30))
        host.dispatch("on_message", "x")
        # 本轮按快照遍历：doomed 仍收到，late-handler 不参与，无人重复/遗漏
        self.assertEqual(log, [("doomed", "boom")])
        host.dispatch("on_message", "y")
        # 下一轮起：doomed 已摘除，late-handler 在册
        self.assertEqual(log, [("doomed", "boom"), ("late-handler", "boom")])
        self.assertEqual(len(host.diagnostics), 2)

    def test_unregistered_plugin_gets_no_further_hooks(self):
        # 一轮内被注销的插件仍按快照跑完本轮；它抛错时诊断照记，
        # 但 on_error 只发给仍在册的插件
        host = PluginHost()
        log = []
        boom_log = []
        boom = Boom("boom", 10, log=boom_log)

        class Unregisterer(Plugin):
            name = "unreg"
            priority = 0

            def on_message(self, message):
                host.unregister(boom)
                return None

            def on_error(self, diag):
                log.append(("on_error", self.name, diag.plugin))

        host.register(Unregisterer())
        host.register(boom)
        out = host.dispatch("on_message", "x")
        self.assertEqual(out, "x")
        self.assertEqual([d.plugin for d in host.diagnostics], ["boom"])
        self.assertEqual(log, [("on_error", "unreg", "boom")])
        self.assertEqual(boom_log, [])  # 已注销，收不到 on_error


if __name__ == "__main__":
    unittest.main()
