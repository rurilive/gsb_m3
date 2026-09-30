# huffx

朴素哈夫曼编码工具，纯标准库，无外部依赖。

## 现状

huffx/tree.py 提供 HuffmanTree 与 build_frequency：

- build_frequency(text)：统计文本里每个符号出现的次数
- HuffmanTree(frequencies)：给定符号到频次的映射，构建哈夫曼树并生成前缀码
- codes()：取回符号到码字的映射，对外只读
- code_table()：按码长升序、码长相同按符号序给出码表条目
- symbols()：取回参与编码的符号，升序
- rescan_count()：线性重扫节点的次数
- encode(text)：把文本逐字符编成零一串
- decode(bits)：把零一串按树还原成文本
- weighted_path_length()：加权路径长度，频次乘码长之和
- average_length()：平均码长
- fixed_width() 与 naive_average_length()：逐字符定长编码的口径与平均码长

内部每合并一步就把仍然可用的全部节点整表重扫一遍，线性挑出频次最小的两个，
规模一大就是平方级，也没有独立的堆结构，但结果正确。

## 问题

用来挑最小频次的只有一次次线性重扫，符号一多、合并轮数一长就明显变慢；
没有独立的堆容器，最小堆的取出与放回无法单独表达，堆操作次数也无从观察；
规范哈夫曼码没有，靠码长就能在两端复现同一套码的路子缺失；k 叉哈夫曼也做不了；
与逐字符定长口径的对照只有平均码长一个数，堆操作次数与朴素重扫次数的差距没有暴露。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_tree.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
