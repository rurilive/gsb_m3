# webpath

站内 HTTP 风格的方法+路径路由器，纯标准库，无外部依赖。

## 现状

`webpath/router.py` 提供 `Router`：

- `add_route(method, path, handler)` 按注册顺序保存路由
- `resolve(method, path)` 返回 `(handler, params)`，`{param}` 段提取路径参数
- 无匹配抛 `NotFound`

## 问题

解析只认注册顺序：静态路由如果注册在动态路由之后，永远轮不到它（`/users/new` 被 `/users/{id}` 抢走，复现见 `python3 demo.py`）。另外打错方法与打错路径报的是同一种 404，排查时无法区分。

## 目标

见任务描述。约束：

- `tests/test_router.py` 是行为基线，一个字不改
- 默认行为（严格尾斜杠、NotFound 语义）不变，新能力全部通过新增配置与异常表达
- 纯标准库

## 运行

```bash
python3 demo.py                          # 路由解析演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 优先级：按路由静态段数量降序匹配，静态段数相同按注册顺序（`sorted` 稳定排序保证）。
- 因此 `/users/new` 无论注册早晚都优先于 `/users/{id}`；同形状并列仍先到先得。
- 尾斜杠：`Router(trailing="strict")`（默认）要求精确一致，行为与旧版相同。
- `trailing="redirect"` 时 `resolve` 返回 `(handler, params, need_redirect)`：
  原路径命中为 `False`；去/补一个尾斜杠后命中为 `True`；两种形态都不中抛 `NotFound`。
- Http405：方法无匹配时，检查其它方法下是否存在同形状路由（段数相同且静态段逐一相等，
  参数段不比较值）；存在则抛 `Http405`，`allow` 为按注册顺序去重的方法列表。
- `Http405` 继承 `NotFound`，旧代码的 `except NotFound` 不受影响；无任何同形状路由仍是 404。
