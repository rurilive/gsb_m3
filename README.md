# quotatree

团队配额管理，纯标准库，无外部依赖。

## 现状

- `quotatree/manager.py` 提供扁平的 `QuotaManager`：
  - `register(team, limit)`：给团队定死额度，重复注册抛 `ValueError`
  - `acquire(team, amount, req_id=None)`：申请，可用额够就扣下来返回 `True`，不够返回 `False`，不欠账
  - `release(team, amount, req_id=None)`：归还，归还量超过当前占用抛 `ValueError`
  - `available(team)` / `used(team)` / `limit(team)` / `teams()`
  - 同一个 `req_id` 重复提交只算一次账：重试直接拿首次的结果，额度不重复动，被拒过的请求重试也还是被拒
  - 请求 ID 被换了参数复用会抛 `ValueError`
- `quotatree/ledger.py` 提供 `Ledger`：申请、归还、重放都留一条流水，含被拒的，`entries()` / `by_team()` / `stats()` 可查
- `quotatree/errors.py` 放异常类型，操作没注册过的团队抛 `UnknownTeam`

## 目标

见任务描述。约束：

- 现有接口行为与 `tests/` 下的基线测试保持不变（基线一个字不改）
- 纯标准库，不引入三方依赖

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
