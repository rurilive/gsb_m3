# steadyclock

巡检工具的时间底座：超时、耗时、跟对端对表都从这里读时间。纯标准库，
无外部依赖，运行环境没有网络，时钟与网络往返全部由模拟器注入。

## 现状

`steadyclock/source.py` 定义时间源：

- `TimeSource` 两个读法加一个前进动作：`wall()` 墙上钟、
  `monotonic()` 单调钟、`sleep(seconds)`
- `SystemSource` 接内核时钟，生产口径
- `ManualSource` 手动时钟，演示与测试用：`sleep` 让两个读法一起前进，
  `step_wall(delta)` 与 `set_wall(value)` 只拨墙钟，模拟一次校时

`steadyclock/deadline.py` 提供两个常用件：

- `Deadline(source, timeout)`：`elapsed()`、`remaining()`、`expired()`、
  `extend(seconds)`、`reset()`，起止差从注入的时间源上取
- `Stopwatch(source)`：`elapsed()`、`restart()`

`steadyclock/simclock.py` 是对端与链路的模拟：

- `PeerClock(true_offset, drift)`：对端墙上钟，挂在本地单调时间轴上
- `Link(base_delay, jitter, skew, spike_chance, spike_factor,
  fault_chance, fault_shift, seed)`：给一次往返抽签，产出两条单向时延、
  排队尖峰与对端错读，`spikes` 与 `faults` 记累计次数
- `Loopback(source, peer, link, service)`：`exchange()` 跑一次往返，
  交出 `(t0, t1, t2, t3)` 四个时间戳

`steadyclock/estimator.py` 提供 `OffsetProbe(loopback)`，`probe()` 单发
估计一次对端与本机的钟差。

## 单调口径与多次估计

超时、耗时与本地打戳一律走 `monotonic()`，校时拨不动：

- `Deadline` 与 `Stopwatch` 的起止差从单调钟上取，墙钟回拨不再假死、
  前跳不再秒断
- `Loopback` 的本地两个戳打在单调钟上，与对端墙上钟同一根时间轴

`steadyclock/estimator.py` 的 `OffsetEstimator(loopback, window)` 把
单发口径升级成多次测量：每趟往返算 NTP 式偏移与往返时延，
`sample()` 交出 `Estimate(offset, error_bound, confidence)`。
`error_bound` 由被选中样本的往返时延一半加散布合成，真值落在界内。

`steadyclock/filter.py` 的 `OffsetFilter` 负责滤波：中位数加 MAD 做
离群剔除，再挑时延最低的一段取中位数做平滑；窗口定长，收敛后不抖，
上万轮不漂、误差界不涨、单轮耗时不涨。

## 目标

见任务描述。约束：

- 纯标准库，装不了三方包，运行环境没有网络
- 既有 API 的签名与语义保持稳定，`tests/` 下的基线一个字节不改，全绿
- `python3 demo.py` 直接跑通

## 运行

```bash
python3 demo.py                          # 时间源、超时、校时与四时间戳演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
