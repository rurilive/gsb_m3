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
- `genheap/generational.py`：`GenerationalHeap`，年轻代/老年代、写屏障记录集、
  minor / major 回收与晋升；`BarrierError` 表示写屏障漏记

## 语义要点

- 对象靠根可达活着；不可达的环、自引用一律收得掉，对象可以指自己
- `on_free(heap, oid, kind, payload)` 在对象从堆里摘掉之后按 oid 升序回调，
  回调里 `alive(oid)` 为假，可以继续 `alloc`、动根
- 本轮新建的对象不在本轮待收名单里，钩子里建的对象留到下一轮
- `stats()["scanned"]` 是历轮标记实际访问过的对象总数
- 正收着时再调 `collect` 抛 `CollectionError`；钩子抛的异常原样往上传，
  堆还能继续用，再收一轮就收敛

## 分代回收

- `genheap/generational.py` 提供 `GenerationalHeap`，接口与 `ObjectHeap` 一致，
  另加 `minor_collect()` / `major_collect()` / `generation(oid)`
- 构造参数 `promote_after`（默认 2）：对象连续 survive 这么多轮回收后晋升老年代；
  `major_threshold` 非空时 `collect()` 在老年代攒够新增量后自动升级成 major
- 新对象进年轻代；minor 只从年轻代根和记录集出发，标记绝不走进老年代，
  扫描量是年轻代的常数倍，与老年代大小无关
- 老年代新指向年轻代的写入由 store 内置写屏障记入记录集；记账按源对象折叠，
  反复改引用不膨胀，清空引用即时收缩，major 全量重建
- 老年代垃圾 minor 不碰，`major_collect()` 全堆标记清除；major 后存活集合
  与全量标记清除完全一致
- `GenerationalHeap(verify=True)` 每轮 minor 后复核屏障记账，漏记跨代引用
  抛 `BarrierError`；生产用 `verify=False`，测试与排障时打开
- 报告新增 `kind` / `promoted` / `young_scanned` / `old_scanned`，
  `stats()` 增加 `young` / `old` / `minor_collections` / `major_collections` /
  `promotions` / `remembered` 等账目

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
