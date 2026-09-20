# walg

账本服务的单机预写日志，纯标准库。

- `walg/wal.py`：`WriteAheadLog.append()` 追加记录并同步刷盘，`read_from()` 按 LSN 重放
- `tests/test_wal.py`：行为与磁盘格式基线
- `demo.py`：顺序写入演示

## 组提交设计

- 单一后台写线程：`append()` 只入队并等待 `Event`，写线程按入队顺序分配 LSN 并写盘，重放顺序即写入顺序。
- 批次怎么切：批内第一条（leader）开 `group_wait`（默认 2ms）宽限窗，并发请求凑进同一批；满 `batch_size`（默认 128 条）或 `batch_bytes`（默认 256KB）立即开刷，参数均可在构造时调整。
- 一批只做一次 `write` + 一次 `fsync`；所有调用方在刷盘完成后才被唤醒，`append` 返回即已落盘。
- 等待全程走条件变量睡眠（deadline 循环，不被入队 notify 提前唤醒），无忙等；`close()` 先刷完在飞批次再退出。
- 失败处理：一次 `write`/`fsync` 失败，整批及队列中等待者收到同一个 `OSError`，不存在部分成功；之后 WAL 进入故障态拒绝写入。
- 崩溃恢复：未刷完整的残尾在打开时截掉，LSN 从最后一条完整记录续号，磁盘格式不变，老日志直接可读。
