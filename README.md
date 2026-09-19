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
