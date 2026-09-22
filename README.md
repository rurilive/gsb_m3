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

## 组织树实现

`quotatree/tree.py` 提供 `QuotaTree`，把总额度挂成一棵组织树：

- `QuotaTree(total)`：建根，根的份额就是总额度
- `add_node(name, parent, limit)`：从父团队闲置里划份额挂团队，闲置不够抛 `ValueError`
- `acquire(name, amount, req_id=None)`：先用自有闲置份额，不够沿祖先链就近借闲置顶上，
  一路借到根还不够才拒（返回 `False`）；借出记在各级祖先的 `lent` 上
- `release(name, amount, req_id=None)`：归还先还借来的部分（按借入明细逐笔还给祖先），
  再退自有份额；归还量超过当前占用抛 `ValueError`
- `available(name)`：自身闲置加各级祖先闲置，即此刻最多能申请的量
- `shrink(name, new_limit)`：缩份额，收走的额度沿祖先链一起减掉（整棵子树都够不着），
  占用压不住的部分缩不动就停住；返回被压到没余量、新申请会被拒的团队清单
- 同一个 `req_id` 重复提交只算一次账，重试拿首次结果，重复归还不会把可用额顶过上限；
  申请、归还、重放都走 `Ledger` 留痕

实现要点：每个节点只维护自用、借出、借入、下级份额合计四个滚动计数和一张借入明细表，
节点不变量为 `自用 + 下级份额之和 + 借出 <= 自身份额`。申请、归还、查可用、缩容的汇总
都只走祖先链（O(树深)），不扫子树；`shrink` 找没余量的团队时按
`子节点可用额 = 父节点可用额 + 自身闲置` 剪枝，可用额大于 0 的分支整棵跳过。
`tests/test_tree.py` 用固定种子的随机借还序列跟逐层重算的参考实现逐节点对拍，
压力测试持续采样两条不变量（占用不超额度、下级之和加自用不超上级），
一万五千节点十万次借还约 0.6s 跑完（限制 10s）。
