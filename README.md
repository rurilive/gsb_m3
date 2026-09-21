# bytetok

字节级分词器，纯标准库，无外部依赖。文本一律先转 UTF-8 字节再处理，
输入也可以是任意字节串（含非法 UTF-8 与随机二进制内容）。

## 模块

- `bytetok/units.py`：切段。ASCII 空白与 ASCII 标点算分隔字节，其余字节
  （含 0x80 以上，多字节 UTF-8 与 CJK 标点都落在这里）算词字节；同类字节
  的最长连续段为一个段，`split_segments(data)` 返回段列表，`join_segments`
  能把段原样拼回，`segment_frequencies(data)` 给按频次降序的段频次。
- `bytetok/vocab.py`：`Vocabulary`，起始 256 个字节 token，id 与字节值
  一一对应。`add(token)` 追加新 token（已存在返回原 id，空串抛
  `ValueError`），`token(id)` / `token_id(token)` 双向查询，`tokens()`
  给按 id 升序的快照。
- `bytetok/tokenizer.py`：`Tokenizer(vocab)`，`encode(text)` 收 str，
  `encode_bytes(data)` 收 bytes，`decode(ids)` 还原字节串，`segments(text)`
  看切段结果；词表带合并规则时编码走 BPE，无规则时逐字节。
- `bytetok/train.py`：`train_bpe(data, vocab, target_size)`，在字节串上
  学 BPE 合并，原地扩充词表并返回按学习顺序排列的规则。
- `bytetok/reference.py`：`naive_encode` / `naive_decode`，朴素逐字节参考
  实现，是编码结果的地面真值。

## 运行

```bash
python3 demo.py                           # 切段、编码解码、与参考实现对拍
python3 -m unittest discover -s tests     # 行为基线
```

## 目标

见任务描述。约束：现有行为与 `tests/` 基线保持不变（基线一个字不改），
纯标准库。

## BPE 实现说明

- 训练先按空白/标点切段并统计段频次；相邻字节对只在段内计数、从不跨段。
- 每轮取全局频次最高的对合并，新 token 追加进词表，规则按学习顺序保存。
- 平票写死可复现：频次相同时取 `(左 token, 右 token)` 字节字典序最小者。
- 同一轮同段多处命中按位置左到右应用，重叠命中只合并最左一处。
- 增量维护：段用链表，"对→命中位置"倒排 + 懒删除堆，只更新受影响邻接对，不做每轮全量重扫。
- 编码按规则优先级反复合并，与训练同口径；未覆盖字节退回逐字节 id。
- 特殊标记最长优先（同长按标记字节升序）整段保留，不参与合并，解码原样还原。
- `Vocabulary.save/load` 为行式文本（base64 字节），持久化 id、合并与特殊标记。
