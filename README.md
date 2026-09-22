# snapwatch

轮询式目录监听，纯标准库，无外部依赖。隔一段时间扫一遍目录树，跟前一次快照
比对，把差异变成事件交给调用方。适合挂载盘、网络盘这类不支持 inotify 的地方。

## 用法

```python
from snapwatch import Watcher

watcher = Watcher("/data/builds")
watcher.subscribe(lambda event: print(event))
watcher.start()          # 后台线程按 interval 反复扫描
...
watcher.stop()
```

也可以自己控制节奏，按批次拿事件：

```python
events = watcher.poll()  # 扫一遍，返回这批事件，同时喂给回调
```

- `Watcher(root, fs=None, clock=time.time, interval=0.5, debounce=0.25, resolution=1.0)`：`fs` 是文件系统
  访问的替身（默认 `SysFS`），`clock` 是时钟，默认挂钟，和文件 mtime 在同一根
  时间轴上；测试里可以换成 `snapwatch.ManualClock`
  - `debounce`：变化静默这么多秒之后才发布，静默期内又变就重新计时，变回
    已发布状态时取消挂起。同一路径在一个发布周期内的多次变化只发净效果，
    周期内出现又消失的路径不发事件
  - `resolution`：文件系统 mtime 的精度（秒）。见下面"时间戳精度"一节
- `poll()`：扫一遍并返回事件列表，回调按同一顺序逐个收到同一批事件对象
- `subscribe(callback)`：挂回调
- `start()` / `stop()`：后台线程模式，stop 可以重复调
- `snapshot()`：最近一次扫描的 `Snapshot`；`last_poll_at`：最近一次
  poll 的时钟读数
- 构造时先扫一次，用来打底，之后 `poll()` 只报真正的变化

事件类型四种：`created`、`modified`、`deleted`、`moved`。`moved` 的 `path`
是旧路径，`dest` 是新路径。事件对象有 `kind`、`path`、`dest`、`is_dir`。
同一个 inode 从旧路径消失、在新路径出现时配成一条 `moved`；原子改名
（写临时文件再 `os.replace` 盖到已有文件上）因为新路径原本就在，报一条
`modified` 而不是 `deleted` + `created`。临时文件即使被中间某轮扫描看见，
也会在配对完成后静默。批内顺序固定为：`deleted`（深的在前、子先于父）、
`modified`、`moved`、`created`（浅的在前、父先于子），同类按路径排。

目录能 `stat` 到但 `scandir` 失败（比如被 chmod 掉权限）时，整棵子树按
"看不清楚、维持原状"处理，不会误报成一片 `deleted`；权限恢复后照常报真实
变化。

`snapwatch/scanner.py` 里的 `PollScanner(fs, root).scan()` 单独也能用，返回
`Snapshot`，用相对 root 的 posix 路径做键，`entry(path)` 拿 `Entry`
（`is_dir`、`size`、`mtime_ns`、`inode`、`digest`，digest 是内容的 sha256）。

## 对拍工具

`snapwatch/reference.py` 里有一套对拍用的东西：

- `OpScript(root, clock, granularity=1.0, seed=1)`：在真实目录上做随机文件
  操作（建、写、追加、删、改名、原子替换、改时间戳、建目录），每一步之后把
  可观测状态记进操作日志。它按 `granularity` 秒的时间片给文件打 mtime，
  这样时间戳精度不靠真机
- `OpReference(debounce=0.25)`：只看操作日志，`prime(存量状态)` 打底，
  之后每轮 `feed(now, ops)` 返回这一轮 `poll()` 该给出的事件列表
- `state_of(path)`：路径当前的可观测状态；`publish`、`sort_key`：把净变化
  收成一批排好序的事件，OpReference 内部用它们出基准

## 时间戳精度

不是所有文件系统的 mtime 都到纳秒：很多挂载盘、网络盘、老的 FAT 盘只有秒
级甚至两秒精度。这种盘上，同一秒里连写两笔、文件大小又没变，只看 mtime 和
size 会把第二笔漏掉。snapwatch 的处理方式是：

- 判定变化以五元组 `(is_dir, size, mtime_ns, inode, digest)` 为准，digest
  是内容的 sha256；
- 静止树扫一轮只读目录元数据，**不读任何文件内容**。只有以下情况才给单个
  文件算一次 digest：新出现的路径、`size/mtime/inode` 任一变了、文件 mtime
  还在 `resolution` 秒的精度窗口内（可能同片再写）、或者该路径上一轮已有
  挂起的变化。十万文件的静止树一轮扫描没有一次文件读取，几秒内跑完；
- `resolution` 按盘的实际 mtime 精度给（默认 1.0 秒；两秒精度的盘给 2.0，
  虚拟时钟对拍时跟 `OpScript(granularity=...)` 对齐）。窗口之外只认元数据，
  不额外读内容。

如果写盘时刻意把 mtime 回拨到精度窗口之外（比当前扫描时刻还早超过
`resolution` 秒）且内容长度不变，轮询方案在元数据层面无信号，这种检测不到
的情况属于轮询的固有边界。

## 运行

```bash
python3 demo.py                          # 现状演示，四类现场
python3 -m unittest discover -s tests -v # 行为基线测试
```
