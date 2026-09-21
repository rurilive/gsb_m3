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

- `Watcher(root, fs=None, clock=time.time, interval=0.5, debounce=0.25)`：
  `fs` 是文件系统
  访问的替身（默认 `SysFS`），`clock` 是时钟，默认挂钟，和文件 mtime 在同一根
  时间轴上；测试里可以换成 `snapwatch.ManualClock`；`debounce` 是静默期秒数，
  一条变化要稳定这么久才发布，期间又变了就从最后一次变化重新计时
- `poll()`：扫一遍并返回事件列表，回调按同一顺序逐个收到同一批事件对象
- `subscribe(callback)`：挂回调
- `start()` / `stop()`：后台线程模式，stop 可以重复调
- `snapshot()`：最近一次扫描的 `Snapshot`；`last_poll_at`：最近一次
  poll 的时钟读数
- 构造时先扫一次，用来打底，之后 `poll()` 只报真正的变化

事件类型四种：`created`、`modified`、`deleted`、`moved`。`moved` 的 `path`
是旧路径，`dest` 是新路径。事件对象有 `kind`、`path`、`dest`、`is_dir`。

变化的合并和发布规则（和 `reference.py` 的基准一致）：

- 同一路径在静默 `debounce` 秒内的连写合并成一条净效果事件；静默期里又变了
  就从最后一次变化重新计时，所以连写三笔只报一条 `modified`
- 一轮扫描里出现又消失的路径不报；变化在发布前改回原样的也不报
- 同一个 inode 从旧路径消失、在新路径出现且新路径原本不存在时，配成一条
  `moved`；新路径原本就在（编辑器先写临时文件再原子改名盖上去）按
  `modified` 算，不会再报 `deleted` + `created`
- 目录被 chmod 掉读权限（`scandir` 失败）时，整棵子树沿用上一份快照，
  不会把没动过的文件误报成 `deleted`；权限恢复后再按真实差异出事件
- 批内顺序固定为 `deleted`（深的在前，子先于父）、`modified`、`moved`、
  `created`（浅的在前，父先于子），同类按路径排序

`snapwatch/scanner.py` 里的 `PollScanner(fs, root).scan()` 单独也能用，返回
`Snapshot`，用相对 root 的 posix 路径做键，`entry(path)` 拿 `Entry`
（`is_dir`、`size`、`mtime_ns`、`inode`、`digest`，digest 是内容的 sha256）。
扫描阶段只做 `stat`/`scandir`，绝不读文件内容；`digest` 在访问时才算并缓存，
所以十万级文件的目录静止时扫一轮也在秒级以内、零读盘。

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

## 运行

```bash
python3 demo.py                          # 四类现场的事件演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 时间戳精度怎么处理

判断文件变没变，主要靠 `(mtime_ns, size, inode)` 三个 stat 字段，扫描本身
不读文件内容。但有些文件系统（挂载盘、网络盘、老式 FAT）时间戳只到整秒，
同一秒里连改两笔、长度又没变时，mtime 和 size 都不动，纯比元数据会漏掉
第二笔。

snapwatch 的做法是设一个"精度存疑窗口"（`CONTENT_WINDOW_SECONDS`，默认
5 秒）：文件 mtime 落在当前时刻的这个窗口以内时，认为它还可能被同秒改写，
必要时读一次内容用 sha256 `digest` 做最终裁决；mtime 老于窗口的文件只信
元数据，静止大树扫描时没有任何内容读取。只改时间戳（touch）而内容不变时，
digest 一致，不会误报 `modified`。

配合 `debounce` 静默期，连续扫描里每次裁决都能看到最新内容：一笔变化在
窗口内的每轮扫描最多读这一个文件一次，发布之后就回到纯元数据路径。轮询
间隔建议明显小于窗口（默认 `interval=0.5`），这样秒级时间戳的盘上"同秒、
同长度、内容不同"的连写也不会漏。窗口长度是纯本地启发式常量，不影响事件
语义，只影响对年轻文件读内容的积极程度；面对更粗粒度的时间戳或更长的
扫描间隔，可以调大 `snapwatch.watcher.CONTENT_WINDOW_SECONDS`。
