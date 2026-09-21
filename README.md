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
  给按 id 升序的快照。`add_special(token)` 登记特殊标记（str 按 UTF-8
  编码），`special_tokens()` / `special_ids()` 按登记顺序查询；
  `save(path|file)` / `Vocabulary.load(path|file)` 二进制往返，id 一致。
- `bytetok/tokenizer.py`：`Tokenizer(vocab, merges=())`，`encode(text)`
  收 str，`encode_bytes(data)` 收 bytes，`decode(ids)` 还原字节串，
  `segments(text)` 看切段结果。`merges` 为 `train_bpe` 返回的按学习
  顺序排列的 `(左id, 右id)` 规则；特殊标记整段保留、不参与合并，
  未覆盖字节退回逐字节，无合并时与 `naive_encode` 逐项一致。
- `bytetok/train.py`：`train_bpe(data, vocab, target_size)`，在 bytes
  语料上迭代合并到目标词表，原地追加新 token，按学习顺序返回规则。
- `bytetok/reference.py`：`naive_encode` / `naive_decode`，朴素逐字节参考
  实现，是编码结果的地面真值。

## 运行

```bash
python3 demo.py                           # 切段、编码解码、与参考实现对拍
python3 -m unittest discover -s tests     # 行为基线
```

## BPE 实现说明

- 合并只发生在 `split_segments` 切出的段内，绝不跨空白/标点边界。
- 频次按相邻对出现位置计，同一段出现 n 次贡献 n 倍；每轮选频次最高
  的相邻 id 对，平票按 `(左 id, 右 id)` 升序写死，段内从最左侧合并。
- 合并产物 = 左 token 字节串 + 右 token 字节串，追加进词表拿下一 id；
  产物已在词表（含特殊标记）时跳过该对，不占一轮。
- 频次表增量维护：用“对 -> 持有段集合”倒排，只重写发生合并的段；
  候选对放最小堆，失效条目惰性删除，不做每轮全量重扫。
- 编码时每轮取学习序号最小的相邻对（平票取最左），无规则可应用即停；
  特殊标记先于切段整段匹配，同位置取更长者，故任意字节序列可逆。
