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

- `Watcher(root, fs=None, clock=time.time, interval=0.5, debounce=0.25,
  timestamp_granularity=1.0)`：`fs` 是文件系统访问的替身（默认 `SysFS`），
  `clock` 是时钟，默认挂钟，和文件 mtime 在同一根时间轴上；测试里可以换成
  `snapwatch.ManualClock`；`debounce` 是静默秒数，`timestamp_granularity`
  是盘上 mtime 的时间片，见文末「时间戳精度」
- `poll()`：扫一遍并返回事件列表，回调按同一顺序逐个收到同一批事件对象
- `subscribe(callback)`：挂回调
- `start()` / `stop()`：后台线程模式，stop 可以重复调
- `snapshot()`：最近一次扫描的 `Snapshot`；`last_poll_at`：最近一次
  poll 的时钟读数
- 构造时先扫一次，用来打底，之后 `poll()` 只报真正的变化

事件类型四种：`created`、`modified`、`deleted`、`moved`。`moved` 的 `path`
是旧路径，`dest` 是新路径。事件对象有 `kind`、`path`、`dest`、`is_dir`。

同一路径在静默期内的多次变化只发一条净效果事件：原子保存（写临时文件再
`os.replace` 盖到原路径）报一条 `modified`，连写多笔也只报最后一笔；一轮
扫描里出现又消失的路径不报。同一个 inode 从旧路径消失、在新路径出现配成
一条 `moved`（两条都不再单独出事件）；新路径原本就存在时按 `modified`
算。一批事件的顺序固定为删除（深的在前、子先于父）、modified、moved、
created（浅的在前、父先于子），同类按路径排。监听目录本身被 chmod 导致
暂时读不出来时，子树沿用上一轮状态，不会被误报成删除。

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

## 运行

```bash
python3 demo.py                          # 修复后演示，四类现场
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 时间戳精度

有些挂载盘、网络盘的 mtime 只精确到秒：同一秒内连改两笔、长度又没变时，
元数据上完全看不出区别，只比 `(mtime, size)` 会漏掉第二笔。snapwatch 的
处理办法是「热时间片读内容」：

- 扫描时默认只 `stat`，不读文件内容，所以十万文件的静止树扫一轮只是元数据
  遍历，几秒内跑完，也不会把冷文件读一遍。
- 一个文件的 mtime 落在「当前扫描时刻所在的 mtime 时间片」内时（即
  `mtime_ns >= now_ns - now_ns % granularity_ns`），认为它可能还在被写，
  这轮读一次内容算 sha256，用内容兜底同时间片内的静默改写；出了这个时间片
  且元数据没再变，就不再读，digest 沿用上一轮观察值。
- 时间片宽度由 `Watcher(..., timestamp_granularity=1.0)` 配置，单位秒，
  默认 1 秒；盘的精度更粗（比如 FAT 是 2 秒）就调大，设成 0 退化成「只看
  元数据、永不主动读内容」。
- 元数据本身变了（inode/size/mtime 任一不同）时一定读一次内容，所以热窗口
  之外的修改不会漏；代价仅限于刚写入的少量热点文件。
- 打底扫描和静默轮询都不读冷文件内容，只有 mtime 还在当前时间片里的文件
  例外。
