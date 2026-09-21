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
