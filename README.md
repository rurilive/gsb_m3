# objlife

页面模型的对象容器，纯标准库，无外部依赖：对象靠引用计数活着，计数归零当场回收并触发销毁回调。

## 用法

```python
from objlife import ObjectStore

died = []
store = ObjectStore(on_destroy=lambda s, oid, kind, payload: died.append(oid))

page = store.create("page", {"name": "home"})  # create 交出来的那份引用已经算上
block = store.create("block")
store.link(page, block)   # page 强引用 block，block 的总引用数加一
store.release(block)      # 放掉调用方手里那份，block 靠 page 活着
store.release(page)       # page 归零，回收；摘出边连锁带走 block
```

## 现有能力

- `objlife/store.py`：`ObjectStore.create` / `retain` / `release` 管外部引用，
  `link` / `unlink` 管对象之间的强引用；计数归零立刻回收，顺序固定为
  摘记录、回调 `on_destroy(store, oid, kind, payload)`、摘出边，
  出边摘除按链式继续，回调里可以继续操作容器
- `objlife/record.py`：`Record`，一个活对象的记账（总引用数 `count`、外部引用数 `ext`、出边）
- `objlife/walk.py`：`reachable` / `layers`，从一组根出发的只读遍历，迭代实现
- `objlife/errors.py`：`StoreError` / `UnknownObject` / `RefCountError` / `LinkError`
- 查询口：`alive` / `refcount` / `retain_count` / `kind` / `payload` /
  `out_links` / `ids` / `roots` / `stats` / `set_hook`

## 现状

回收只认计数归零这一条路：互相引用的节点谁都不会先到零，全留在容器里；
旁路持有的引用也只能用外部引用表达，会把对象钉住。

## 目标

见任务描述。约束：现有接口与 `tests/` 基线行为保持不变，纯标准库。

## 运行

```bash
python3 demo.py                          # 建图、放引用、看回收与可达子图
python3 -m unittest discover -s tests -v # 行为基线测试
```
