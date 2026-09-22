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

## 组织树实现（QuotaTree）

`quotatree/tree.py` 把事业部挂上组织树，接口：

- `QuotaTree(total, ledger=None, root_name="root")`：建根，总额度 `total`
- `add_node(name, parent, limit)`：从父节点闲置里划份额，划不出抛 `ValueError`
- `acquire(name, amount, req_id=None)` / `release(name, amount, req_id=None)`：申请与归还
- `available(name)`：当前能申请到的最大量；另有 `used` / `limit` / `borrowed` /
  `effective` / `free` / `nodes` / `children` / `parent` 可读
- `shrink(name, new_limit)`：缩份额，返回被压到没余量的团队清单

模型：

- 每个节点：基础份额 `limit` + 临时借入 `borrowed` = 可支配总额度 `effective`；
  自留闲置 `free = effective - 自用 - 下级份额之和`，恒不为负。
  两条不变式：占用不超额度（`self_used <= effective`）、下级之和加自用不超上级。
- 申请先吃自留闲置，不够沿祖先链逐级借：父节点闲置够就直接顶上，不够它自己
  再向上借，一路到根；根闲置不够就整笔拒掉，不欠账。
- 归还先还借的：释放的占用先冲抵 `borrowed`，借来的份额逐级还回上级池子。
- `available(name)` = 自留闲置 + 沿祖先链可借的闲置之和，与 `acquire` 的成败
  判定完全一致。
- `shrink` 只收闲置：下限 = 自用 + 下级份额 - 借入，`new_limit` 低于下限就停在
  下限。缩中间节点只是把闲置还进父池，子树整体可借总量不变，返回空；缩根等于
  砍总预算，可用额从正变零的团队（含根本身）按名字升序返回。
- `req_id` 幂等语义与 `QuotaManager` 一致：重复提交只算一次账，重试拿首次结果，
  被拒过的重试还是被拒，换参数复用同一 ID 抛 `ValueError`；重复归还不会把可用额
  顶过上限。申请、归还、重放都走 `Ledger` 流水。

性能：下级份额汇总 `children_eff` 挂在节点上就地维护，借还与缩容只沿祖先链走
O(深度)，不扫子树。`tests/test_tree.py` 用固定种子随机借还序列跟逐层重算的参考
实现逐节点对拍，另有一万五千节点、十万次借还的压力测试（秒级完成，限制 10s），
过程中持续采样校验上面两条不变式。
