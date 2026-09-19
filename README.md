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

`python3 -m unittest discover -s tests`：25 个测试方法，17 绿、8 红
（k 构造用例含 5 组参数子用例，unittest 汇总为 11 failures + 1 error）。红用例均在
`tests/test_bloom.py` 中以 `_is_red` 命名并在上方注明了 README 期望与实际
行为。`python3 demo.py` 照常跑通，`bloomx/` 源码与 `demo.py` 未改动。

| 红用例 | 缺陷 | 建议修复方向 |
| --- | --- | --- |
| `test_invalid_capacity_noninteger_is_red` | `__init__` 只查 `capacity <= 0`，非整数 capacity（如 1.5）被接受 | 增加正整数校验（`isinstance(capacity, int)` 且 `capacity > 0`），否则 ValueError |
| `test_num_hashes_formula_is_red` | k 的计算用 `log10(2)` 代替 ln2、`int()` 截断且缺少 `max(1, ...)`，得到 2/4/0 等错误值 | 改为 `max(1, round((m / capacity) * math.log(2)))` |
| `test_h2_depends_on_every_byte_is_red` | `_mix` 中 h2 的更新式 `((h2 * 31)) & mask` 从未使用当前字节，等长输入的 h2 恒为常数 | 让 h2 的更新依赖字节 b（如异或/相加后再乘质数） |
| `test_distinct_elements_probe_sequences_differ_is_red` | h2 与字节无关，`b'\x00a'` 与 `b'\x01\x00'` 的 (h1, h2) 完全相同，探测序列逐位重合 | 修复 h2 的字节依赖后该碰撞即消失，必要时再复核 h1 的混合强度 |
| `test_empty_filter_membership_is_red` | 首次 add 前 `_bits` 是长度 0 的 bytearray，空过滤器上 `in` 抛 IndexError | 构造时即分配完整位数组（或 `__contains__` 在未分配时直接返回 False） |
| `test_estimated_fp_uses_readme_k_is_red` | 因 k 被算成 2，容量打满时理论误判率约 0.0355（实测约 2.6%~3.5%），而非 README 公式的约 0.0100 | 根因同 k 计算缺陷，按 README 公式修正 k 后估计值即回归目标误判率 |
| `test_loads_restores_fields_is_red` | `loads` 按 `(magic, num_hashes, num_bits, added)` 接收解包结果，把头中的 m、k 互换 | 改为 `magic, num_bits, num_hashes, added = _HEADER.unpack_from(...)` |
| `test_loads_membership_equivalent_is_red` | m、k 互换后用错误参数探测，已加入的键 loads 后全部查不到 | 根因同 loads 字段互换，修正解包顺序后往返行为一致 |

绿用例覆盖：非法 fp_rate、m 构造公式、属性只读、元素类型与 UTF-8 编码、
add/`in` 共用探测函数、double hashing 探测公式、固定输入无假阴性、重复 add
计数不去重、空过滤器 estimated_fp 为 0、固定输入实测误判率与估计值同量级、
28 字节头布局（magic + 三个大端 Q）、载荷为位数组原样字节、坏 magic 抛
ValueError。
