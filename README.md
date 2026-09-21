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
```

约束：

- 名字限 ASCII 字母数字与 `.` `_` `-`，首字符必须是字母或数字，最长 64
- `put` 只收字节串，传 `str` 抛 `TypeError`
- 名字区分大小写；按前两位字符分片存放

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 回收时机与失败记账

对象按内容 sha256 存于 `objects/`，名字只是 `index/` 下指向摘要的引用。
相同字节全库只落一份；`put` 同名改内容只是换引用，旧对象留在原地。
`delete` 只减引用，绝不当场删对象，保证并发读和覆盖写都不会弄丢内容。
对象只在显式调用 `gc()` 时回收：先扫全部引用算出存活摘要，再删无主对象。
`gc()` 删失败的对象逐行记入 `gc/pending`，下次调用先重试历史欠账再收新垃圾。
欠账对象若被新名字重新指回则视为存活，本次回收当场勾销，绝不误删。
引用损坏导致无法判断存活时，`gc()` 抛 `CorruptObject` 且一个对象都不删。
读取时重新计算摘要比对，对象被改坏或丢失也抛 `CorruptObject`，不交出错字节。
所有落盘先写 `.bvtmp` 临时文件再原子改名；重开库时只清扫自己的临时文件。
`stats()` 返回 `{"objects", "names", "bytes"}`：对象数、名字数与对象占用字节。
