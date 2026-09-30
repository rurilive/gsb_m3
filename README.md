# pathcount

一个有向图定长路径计数的小库，只用 Python 标准库，无外部依赖。

## 现状

pathcount/count.py 提供 DirectedGraph 与 PathCounter 两个类，构造期一次
建成邻接表与邻接矩阵，之后图不再变动。能用的是最直白的一条路：

- DirectedGraph：节点用整数编号，允许重边与自环；nodes 按登记顺序、edges
  按 u、v 升序、adjacency_matrix 给出邻接矩阵、out_neighbors 给直接后继
- count_walks_exact：恰好走 steps 步的走法数，从起点逐层深度搜索，把每条
  走法整条枚举出来再计数
- count_paths_between：两点之间全部简单路径的条数，同样靠深度搜索枚举
- count_walks_up_to：长度不超过 bound 的走法数，对每个长度各枚举一遍累加
- has_cycle_of_length / shortest_cycle：按长度从小到大枚举判定回路存在与最短
- mat_mul / mat_pow：三重循环的矩阵乘法、逐次相乘的矩阵幂

每次查询开始前把 depth_steps、enum_paths、mult_count 归零后重新累加。

## 问题

步数或点数一多就是指数乃至立方量级地退下去：走法数靠把每条走法整条枚举，
步数每加一，搜索量就乘上一个出度；矩阵幂是指数多大就做多少次乘法，每次
乘法又是立方量级的循环，大基数下既慢又没有任何计数能把两路的规模摆在一起
对照，新算出来的结果也没有拿回基线核验过。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_count.py 基线保持一致（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

（实现后补，10 行以内）
