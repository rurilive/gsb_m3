# genheap

纯标准库的标记清除对象堆：对象之间用命名槽位互相引用，根集合由外部注册，
回收时从根出发标记，走不到的对象整片收掉。

## 用法

```python
from genheap import ObjectHeap

freed = []
heap = ObjectHeap(on_free=lambda h, oid, kind, payload: freed.append(oid))

page = heap.alloc("page", {"name": "home"})
block = heap.alloc("block")
heap.add_root(page)                # page 挂进根集合
heap.store(page, "body", block)    # page 的 body 槽位指向 block
heap.store(page, "body", None)     # 清空槽位
heap.collect()                     # 全堆标记清除，返回本轮报告
print(heap.ids(), heap.stats())
```

## 模块

- `genheap/heap.py`：`ObjectHeap`，分配 `alloc`、根集合 `add_root` /
  `drop_root` / `roots`、槽位 `store` / `load` / `slots` / `refs`、
  回收 `collect`、账目 `stats`；`Cell` 是单个活对象的记账
- `genheap/mark.py`：`trace` / `unmarked`，从一组根出发的迭代遍历和待收名单，
  不依赖堆的其余状态
- `genheap/errors.py`：`HeapError` / `UnknownObject` / `RootError` /
  `SlotError` / `CollectionError`

## 语义要点

- 对象靠根可达活着；不可达的环、自引用一律收得掉，对象可以指自己
- `on_free(heap, oid, kind, payload)` 在对象从堆里摘掉之后按 oid 升序回调，
  回调里 `alive(oid)` 为假，可以继续 `alloc`、动根
- 本轮新建的对象不在本轮待收名单里，钩子里建的对象留到下一轮
- `stats()["scanned"]` 是历轮标记实际访问过的对象总数
- 正收着时再调 `collect` 抛 `CollectionError`；钩子抛的异常原样往上传，
  堆还能继续用，再收一轮就收敛

## 现状

回收只有全堆扫一遍这一条路：堆越大每轮的工作量越大，老对象再多也省不掉；
新对象大多活不过一轮，却要陪着老对象一起被完整标记。

## 目标

见任务描述。约束：现有接口语义与 `tests/` 基线保持不变，纯标准库。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
