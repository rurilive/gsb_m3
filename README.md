# bloomx

风控侧内存去重用的布隆过滤器：允许把未加入的元素误判为存在（假阳性），
绝不允许把已加入的元素判为不存在（假阴性）。纯标准库。

## 语义约定（以下为本模块的正式行为定义）

1. **构造与容量约束**
   - `BloomFilter(capacity, fp_rate=0.01)`：capacity 为预期元素个数，必须是
     正整数；fp_rate 为目标误判率，必须落在开区间 (0, 1)，否则 ValueError
   - 位数组大小 m = ceil(-capacity * ln(fp_rate) / ln(2)^2)，哈希个数
     k = max(1, round((m / capacity) * ln 2))；构造完成后只读，通过
     num_bits / num_hashes 属性暴露
2. **哈希与探测**
   - 元素为 str 或 bytes（str 按 UTF-8 编码），其它类型抛 TypeError
   - 采用 double hashing：对编码后的字节派生两个相互独立的基础哈希 h1、h2，
     探测位 idx_i = (h1 + i * h2) mod m（i = 0..k-1）
   - **两个基础哈希必须各自依赖输入的每一个字节**；两个不同元素的探测序列
     不允许完全相同（那会使误判远超估计）
   - add 与 `in` 使用同一探测函数，同一元素两次探测结果一致
3. **FP 语义**
   - 已 add 的元素 `in` 必为 True（无假阴性）
   - 未 add 的元素允许 `in` 为 True（假阳性）；estimated_fp() 返回当前理论
     误判率 (1 - e^(-k*n/m))^k，n 为 add 调用次数（不去重）
   - **空过滤器对任何元素 `in` 必须返回 False，不允许抛异常**
4. **序列化**
   - serialize() -> bytes：28 字节头（magic "BLMX" + m、k、n 三个 8 字节
     无符号整数，大端）+ 位数组原样字节
   - loads(data) 还原出等价过滤器：num_bits、num_hashes、num_added 与位数组
     内容都和原实例一致，还原后继续 add / `in` 行为一致
   - magic 不对的数据 loads 抛 ValueError

## 运行

```bash
python3 demo.py
```

## 测试报告

运行 `python3 -m unittest tests.test_bloom -v`：共 23 个用例，14 绿、9 红
（8 failures + 1 error）。红用例及对应缺陷、修复方向如下：

| 红用例 | 缺陷（与 README 的出入） | 建议修复方向 |
| --- | --- | --- |
| `test_capacity_must_be_integer` | 构造只校验 `capacity > 0`，`10.5` 等非整数被静默接受，未遵守"必须是正整数" | 增加 `isinstance(capacity, int)`（并排除 `bool`）校验，否则抛 ValueError |
| `test_num_hashes_formula` | k 误用 `log10(2)` 且 `int()` 截断：(1000, 0.01) 得 2 而非 7，(100, 0.001) 得 4 而非 10 | 改为 `max(1, round((m / capacity) * math.log(2)))` |
| `test_num_hashes_at_least_one` | 缺少 `max(1, ...)` 下限，(1, 0.5)、(2, 0.5) 构造出 k=0 | 同上行公式修正，k 最小为 1 |
| `test_empty_filter_contains_is_false_without_raise` | 位数组懒分配，空过滤器上 `in` 直接 IndexError，违反"空过滤器必返回 False、不允许抛异常" | 构造时即分配 `bytearray((m + 7) // 8)`，add 中去掉惰性初始化 |
| `test_empty_filter_with_k_zero_still_false` | k=0 时探测循环空转，空过滤器对任何元素都返回 True | 修正 k 公式（保证 k≥1）即可消除 |
| `test_both_base_hashes_depend_on_every_byte` | `_mix` 中 h2 迭代式为 `h2 * 31`、从不读入字节，b"a"/b"b" 的 h2 完全相同 | 每轮把当前字节混入 h2（如 `(h2 * 33) ^ b`），并建议整体换更强的双哈希 |
| `test_distinct_elements_have_distinct_probe_sequences` | h2 只依赖长度叠加 h1 低 8 位 XOR 弱点，b"\x00a" 与 b"\x01\x00" 探测序列完全重合（只加前者后者必命中） | 修 h2 使其逐字节依赖，并强化 h1 的混合（避免高位不受末字节影响） |
| `test_roundtrip_fields` | `loads` 解包顺序写成 `(magic, num_hashes, num_bits, added)`，还原后 m 与 k 对调（9586/2 变 2/9586） | 解包改为 `(magic, num_bits, num_hashes, added)` |
| `test_roundtrip_bits_and_behavior` | m/k 对调后探测位全部错位，已加入元素 loads 后全部判为不存在（假阴性），违反往返等价承诺 | 同上修正解包顺序 |

去重后为 5 处独立缺陷：构造整数校验缺失、k 公式错误（含 k=0）、空过滤器位数组
未分配、h2 不依赖输入字节（含探测序列重合）、loads 头字段 m/k 对调；estimated_fp
公式本身正确（对应用例按实例自身 k/m/n 断言为绿），其输出偏差是 k 公式错误的连带结果。
