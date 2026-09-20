"""PluginHost：插件的注册、注销、排序与钩子调度。"""

from pluginhost.plugin import Plugin


class Diagnostic:
    """一次插件钩子错误的记录：插件名、钩子名、原异常。"""

    def __init__(self, plugin, hook, error):
        self.plugin = plugin
        self.hook = hook
        self.error = error

    def __repr__(self):
        return "Diagnostic(plugin=%r, hook=%r, error=%r)" % (
            self.plugin,
            self.hook,
            self.error,
        )

    def __eq__(self, other):
        return isinstance(other, Diagnostic) and (
            self.plugin,
            self.hook,
            self.error,
        ) == (other.plugin, other.hook, other.error)


class PluginHost:
    """插件宿主。

    提供注册、注销与钩子调度：钩子抛错只跳过出错的插件，错误记入
    diagnostics 并按 priority 触发所有在册插件的 on_error。
    """

    def __init__(self):
        self._plugins = []  # 已按 (priority, 注册序) 排好
        self.diagnostics = []  # Diagnostic 按发生顺序追加

    @property
    def plugins(self):
        """按调用顺序返回插件列表（副本，调用方改不动内部状态）。"""
        return list(self._plugins)

    def __contains__(self, plugin):
        return any(p is plugin for p in self._plugins)

    def __len__(self):
        return len(self._plugins)

    def plugin(self, name):
        """按名字取插件，不存在时抛 KeyError。"""
        for p in self._plugins:
            if p.name == name:
                return p
        raise KeyError(name)

    def register(self, plugin):
        """注册插件：校验、按 priority 插入、回调 on_registered。

        on_registered 抛错时注册回滚（插件不留在宿主上），异常原样上抛。
        """
        if not isinstance(plugin, Plugin):
            raise TypeError("register 需要 Plugin 实例")
        if not plugin.name:
            raise ValueError("插件缺少 name")
        if any(p.name == plugin.name for p in self._plugins):
            raise ValueError("插件名重复: %s" % plugin.name)
        self._insert(plugin)
        try:
            plugin.on_registered(self)
        except BaseException:
            self._plugins.remove(plugin)
            raise

    def unregister(self, plugin):
        """把插件从调用链摘掉：幂等，不在册则静默返回，不触发任何回调。"""
        for i, existing in enumerate(self._plugins):
            if existing is plugin:
                del self._plugins[i]
                return

    def _insert(self, plugin):
        # 按 priority 升序找插入点：同 priority 落在已有插件之后（注册先后）
        index = len(self._plugins)
        for i, existing in enumerate(self._plugins):
            if plugin.priority < existing.priority:
                index = i
                break
        self._plugins.insert(index, plugin)

    def dispatch(self, hook, payload):
        """把 payload 沿插件链依次喂给每个插件的同名钩子。

        - 迭代开始时对插件列表取快照，本轮的注册/注销下一轮才生效
        - 插件没有定义该钩子（无可调用属性）时跳过
        - 钩子返回 None 表示透传当前 payload，否则返回值作为
          下一个插件的输入；最终返回值即 dispatch 的返回值
        - 钩子抛错只跳过该插件：错误记入 diagnostics 并触发 on_error，
          抛错前的 payload 继续往下游传
        """
        for plugin in list(self._plugins):
            method = getattr(plugin, hook, None)
            if not callable(method):
                continue
            try:
                result = method(payload)
            except Exception as exc:
                self._record_error(plugin, hook, exc)
                continue
            if result is not None:
                payload = result
        return payload

    def _record_error(self, plugin, hook, exc):
        """追加一条诊断，然后按 priority 触发所有在册插件的 on_error。"""
        diag = Diagnostic(plugin.name, hook, exc)
        self.diagnostics.append(diag)
        for other in list(self._plugins):
            on_error = getattr(other, "on_error", None)
            if not callable(on_error):
                continue
            try:
                on_error(diag)
            except Exception as err:
                # on_error 再抛错只记 diagnostics，不二次触发
                self.diagnostics.append(Diagnostic(other.name, "on_error", err))
