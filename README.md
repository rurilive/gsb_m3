# stealpool

采集管线在用的进程内任务池，纯标准库，无外部依赖。

## 调度语义

`stealpool/pool.py` 提供 `Pool(workers=None, name="stealpool")`：

- `submit(fn, *args, **kwargs)` 提交任务返回 `Future`；worker 数默认取 CPU 核数
- 每个 worker 一条本地双端队列：**自己从头取、别人从尾偷**。偷的是队列里
  最老的任务，子树通常最大，一次偷走能养活空闲 worker 更久
- worker 里派生的子任务进**自己队列的头部**，下一个就被自己拿到，线程本地
  攒的站点会话和解析缓存用得上；外部提交轮转到各队列尾部，天然摊开
- **等子任务不空等**：worker 在任务里取子任务结果时转成帮忙模式，继续从本地
  队列和别的队列取活干，直到等的那个 future 落定。单 worker 跑深链也不会
  死锁饿死
- **取消级联**：取消一个没跑完的任务，它派生出去还没开跑的子孙任务一并作废，
  取结果抛 `TaskCancelled`；已经在干活的子孙不打断
- 空载和偷不着活时 worker 睡在条件变量上，不忙等烧 CPU
- `shutdown(wait=True)` 关闭并等在跑的任务收尾，可重复调用；关闭后提交抛 `PoolClosed`
- `stats()` 返回快照：submitted / completed / failed / steals，以及每个 worker 的
  busy_seconds / idle_seconds / tasks
- 支持 `with Pool(...) as pool` 写法

`stealpool/future.py` 提供 `Future`：

- 状态从 PENDING 到 RUNNING 再到 FINISHED；还在 PENDING 的可以 `cancel()`，进 CANCELLED
- `result(timeout=None)` 阻塞取结果，任务抛过异常就重新抛出，等超时抛 `TimeoutError`，
  被取消的任务抛 `TaskCancelled`；`done()` / `cancelled()` / `running()` / `state()` 查状态
- `add_done_callback(fn)` 在结束或取消时回调

`stealpool/reference.py` 提供任务树的顺序参考实现：

- `TaskNode(name, children=(), work=0.0, tag=0)`：节点结果等于 tag 加子节点结果之和，
  work 是模拟 IO 的耗时秒数，由注入的 sleep 消耗
- `run_sequential(root, sleep=time.sleep, order=None)`：单线程按后序跑完整棵树，
  返回 name 到结果的字典，order 记录完成顺序
- `random_tree(seed, depth=3, fanout=3, leaf_work=0.0)`：确定性随机任务树
- `TreeRunner(pool, sleep=time.sleep).run(root)`：每个节点一个任务，子节点由父任务
  submit 后取结果，返回和 `run_sequential` 同形状的字典

注意：任务树每层派生要占几层 Python 栈，Pool 创建时会把递归上限抬到 32768，
几千层的深链也跑得完。

## 运行

```bash
python3 demo.py                          # 提交取结果、任务树对拍、取消与窃取演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
