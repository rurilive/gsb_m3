# blobvault

团队文件暂存服务用的本地对象库：把二进制对象按逻辑名字存进一个目录树，
纯标准库，无外部依赖。

## 用法

```python
from blobvault import ObjectStore

store = ObjectStore("data")                 # root 目录，可传 str 或 Path
rel = store.put("contract-a", b"...")       # 写入，返回相对 root 的落盘路径
store.get("contract-a")                     # 读回字节，名字不存在抛 ObjectNotFound
store.delete("contract-a")                  # 删除，返回是否真的删到了
store.list()                                # 全部名字，升序
store.stats()                               # {"objects", "names", "bytes"}
store.gc()                                  # 回收没有名字引用的对象
```

约束：

- 名字限 ASCII 字母数字与 `.` `_` `-`，首字符必须是字母或数字，最长 64
- `put` 只收字节串，传 `str` 抛 `TypeError`
- 名字区分大小写；按前两位字符分片存放

存储模型：字节按 sha256 内容寻址落在 `objects/<前两位>/<摘要>.blob`，
相同字节全库只存一份，逻辑名字只是 `names.idx` 里指向摘要的一条引用。
读回时按登记摘要重新校验；对象被改坏、截断或丢失时抛 `ObjectCorrupted`，
不会把和名字对不上的字节交出去。所有落盘都是先写 `.bvtmp-*` 临时文件再
原子改名；重新打开 store 时只清扫自家遗留的临时半成品，不碰目录里别的东西。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 回收时机与失败记账

1. 删名字只摘引用，`delete` 当场绝不删对象，避免另一个名字仍指向它。
2. 没有任何名字引用的对象要等显式调用 `gc()` 才会真正释放磁盘。
3. `gc()` 删除前会用当前名字索引重算引用集合，仍被引用的对象一律保留。
4. 单个对象删除失败（权限、IO 错误等）不影响其他对象，只把失败项记账。
5. 账本持久化在 `gc-ledger.json`：记录对象摘要、失败次数和最近错误原因。
6. 之后每次 `gc()` 先重试账本里的对象，重试前再次确认它仍无名字引用。
7. 对象在重试前重新被某个名字指上，对应记账立即撤销，永远不会被删。
8. 账本里的对象若已不在盘上则自动销账；全部重试成功后账本文件被删除。
9. 因此索引不会指向已删内容（不会丢内容），盘上也不会长期堆积无主对象。
10. 账本只记账不自动后台清理，失败需要重试时再调一次 `gc()` 即可。
