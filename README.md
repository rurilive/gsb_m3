# pluginhost

进程内插件宿主：插件实现 `Plugin` 基类挂到 `PluginHost` 上，宿主按优先级
调度钩子。单进程内嵌，纯标准库。

## 模块结构

- `pluginhost/plugin.py`：`Plugin` 基类。类属性 `name` / `priority`，
  生命周期回调 `on_registered(host)`，业务钩子示例 `on_message`
- `pluginhost/host.py`：`PluginHost` 的注册、排序与 `dispatch`
- `pluginhost/plugins.py`：内置示例插件（audit / mask / signer），demo 使用

## 调用约定

- 注册：`register(plugin)` 要求 `Plugin` 实例（否则 `TypeError`），
  `name` 非空且唯一（否则 `ValueError`）；`on_registered` 抛错则注册
  回滚（插件不留在宿主上）、异常原样上抛
- 顺序：按 `priority` 升序调用，相同 priority 按注册先后
- `dispatch(hook, payload)`：开始时对插件列表取快照，依次调用每个
  插件的同名可调用属性；没有该属性的插件跳过；钩子返回 None 透传
  当前 payload，返回值作为下一个插件的输入，最终返回值即 dispatch 结果
- 错误行为：v1 为抛错即中断整轮；现状见文末「扩展说明」
- 注销：v1 没有注销接口；`unregister` 见文末「扩展说明」

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 扩展说明

- `unregister(plugin)`：按身份摘除插件，幂等（未注册则静默返回），
  不触发任何回调；重新注册视为全新注册，同 priority 排到队尾
- 错误隔离：业务钩子抛错只跳过该插件，抛错前的 payload 继续传给
  下游，dispatch 正常返回
- 每次错误追加一条 `Diagnostic`（插件名、钩子名、原异常）到
  `host.diagnostics`，按发生顺序
- 每个错误触发 error 生命周期：按调用顺序对所有在册插件调
  `on_error(diag)`；`on_error` 再抛错只记 diagnostics，不二次触发
- dispatch 与 error 事件都按开始时的快照遍历：本轮的注册/注销
  下一轮才生效，回调中增删插件安全
