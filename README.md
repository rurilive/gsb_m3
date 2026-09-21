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

## 新口径

- 超时、耗时与本地打戳一律走单调钟，校时回拨与前跳拨不动它们
- `steadyclock/filter.py` 的 `OffsetFilter`：滑窗内取低时延样本，
  中位数 + MAD 剔离群，幸存样本取均值平滑
- `OffsetEstimator(loopback)` 多次测量，每次 `sample()` 交出
  `Estimate(offset, error_bound, confidence)`
- `error_bound` 按"真值必落在干净样本 ± 其半时延内"兜底，真的兜得住
- 收敛后估计锁定不抖；对端真值迁移（重新校时）时自动解锁重收敛
- 链路有尖峰与错读时估计不被带偏，`confidence` 跟着降
- 单轮开销定长（窗口定长），上万轮采样不漂、界不涨、耗时不涨
- 新行为的测试在 `tests/test_offset_estimator.py`，既有基线未动
- `OffsetProbe` 保留原语义，仅供兼容
- 演示见 `demo.py` 第五段

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
