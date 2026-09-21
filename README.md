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
  看切段结果。
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
