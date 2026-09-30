# huffman

纯标准库的哈夫曼编码工具雏形，纯内存，无外部依赖。

## 现状

huffman/codec.py 提供改造前的朴素实现，挑最小权重全靠一次次线性重扫：

- build_frequency(text)：统计文本里每个符号出现的次数
- HuffmanCodec(weights)：给定符号到非负整数的权重表，重扫建树并生成前缀码
- codes() / code_table() / symbols()：取回码字映射、按码长升序的码表、参与编码的符号
- rescan_count()：线性重扫挑选最小的次数，每建一次树可读一次
- encode(text) / decode(bits)：逐字符编码、按树解码，往返无损
- weighted_path_length() / average_length()：加权路径长度与平均码长
- 模块级 encode / decode / build_codes / weighted_path_length：一次性便捷入口
- NaiveIndexHeap：以线性重扫为底的索引堆，接口与二叉堆一致，元素按 (键, 编号) 字典序比较
- Erro：所有对外异常的公共基类，其下挂 InvalidWeightError / EmptySymbolError /
  UnknownSymbolError / InvalidBitstreamError

权重只接受非负整数，零权重合法，布尔值与非整数一律拒掉；体重并列时按符号下标
字典序确定性合并。

## 问题

用来挑最小权重的只有一次次线性重扫，符号一多就明显变慢；没有以二叉堆为底的
优先队列，取出与放回无法单独表达，堆操作次数也无从观察；并列时如何稳定合并
只有符号这一条口径；单符号、全同权、零权重、空表这些边界也没有被系统覆盖。

## 目标

在当前基础上，以二叉堆优先队列为一趟建树的核心，并让自研堆与标准库堆互为对照，
另留一条朴素线性重扫路对同一批数据逐项印证，见任务描述。约束：

- 现有行为与 tests/test_codec.py 基线保持一致（基线一个字不改）
- 新行为另开 tests/test_heap.py
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

（实现后补，10 行以内）
