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
