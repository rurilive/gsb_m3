# pluginhost

进程内插件宿主：插件实现 `Plugin` 基类挂到 `PluginHost` 上，宿主按优先级
调度钩子。单进程内嵌，纯标准库。

## 模块结构

- `pluginhost/plugin.py`：`Plugin` 基类。类属性 `name` / `priority`，
  生命周期回调 `on_registered(host)`，业务钩子示例 `on_message`
- `pluginhost/host.py`：`PluginHost` 的注册、注销、排序与 `dispatch`
- `pluginhost/plugins.py`：内置示例插件（audit / mask / signer），demo 使用

## 调用约定

- 注册：`register(plugin)` 要求 `Plugin` 实例（否则 `TypeError`），
  `name` 非空且唯一（否则 `ValueError`）；`on_registered` 抛错则注册
  回滚（插件不留在宿主上）、异常原样上抛
- 顺序：按 `priority` 升序调用，相同 priority 按注册先后
- `dispatch(hook, payload)`：开始时对插件列表取快照，依次调用每个
  插件的同名可调用属性；没有该属性的插件跳过；钩子返回 None 透传
  当前 payload，返回值作为下一个插件的输入，最终返回值即 dispatch 结果
- 错误行为：插件钩子抛错只跳过该插件，错误记入 `host.diagnostics`
  并触发 `on_error` 事件，详见末尾「扩展说明」
- 注销：`unregister(plugin)` 幂等摘除，详见末尾「扩展说明」

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 扩展说明

- `unregister(plugin)`：把插件从调用链摘掉，幂等（不在册则静默返回），
  只摘除、不触发任何回调；注销后同名可再注册，重新注册排在同
  priority 末尾而不是回到原位
- 轮次边界：`dispatch` 开始时对调用链取快照，一轮内的注册/注销
  不影响本轮已定好的链，下一轮才生效
- 错误隔离：插件钩子抛错只跳过该插件，抛错前的 payload 继续往下
  游传；错误按发生顺序追加到 `host.diagnostics`，`Diagnostic`
  记插件名、钩子名、原异常
- error 生命周期：记录诊断后按 priority 顺序对所有在册插件调用
  `on_error(diag)`（遍历同样基于快照，回调里注册/注销安全）；
  `on_error` 再抛错只追加 diagnostics，不二次触发
