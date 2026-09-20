# quolease

自研的多数派选主与租约小包，纯标准库，无外部依赖。

## 现状

`quolease/core.py` 提供 `QuorumLease`：

- `QuorumLease(voters, clock=time.monotonic, lease_seconds=10.0)`，voters 是注入的成员表（node -> 是否在线），clock 是注入时钟
- `members()` / `alive_members()` 返回排序后的成员名；成员表归调用方持有，改它就是模拟集群变化
- `quorum_size()` 取全体成员的一半向下取整再加一；`has_quorum()` 看在线成员够不够多数派
- `elect()` 在在线成员里取名字最小的当 leader，凑不齐多数派返回 None 且不动现有 leader；`leader()` / `term()` 读当前状态
- `renew(node)` 让当前 leader 把到期时刻刷成 now + lease_seconds；`lease_expires_at()` 读到期时刻

## 问题

租约时长写死、续租只看是不是 leader，跟多数派完全脱钩。缩容再扩容、网络分区之后，少数派节点照样续租、照样放行写许可。

## 目标

见任务描述。约束：

- `tests/test_quolease.py` 基线一个字不改，必须原样全绿
- 纯标准库

## 运行

```bash
python3 demo.py                          # 选主与续租演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
