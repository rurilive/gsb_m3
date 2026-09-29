# wheelish

纯标准库的定时器与时间轮，无外部依赖。

## 现状

`wheelish/timer.py` 提供列表式定时器 `ListTimer`：

- `ListTimer(clock=None)`：clock 可注入，默认 `time.monotonic`
- `register(delay, payload=None, key=None)`：挂 delay 秒后触发的任务，返回句柄
- `tick(now)`：把时钟推进到 now，返回所有 `deadline <= now` 的到期任务
- `cancel(handle)`：取消任务，已取消或已触发的返回 False

## 问题

待触发任务全放在一个列表里线性扫描：每次 tick 都要遍历全部任务，
注册与取消也都是 O(n)，任务量一大就顶不住。

## 目标

做出分层时间轮，见任务描述。约束：

- 现有行为与 `tests/test_timer.py` 基线保持一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
