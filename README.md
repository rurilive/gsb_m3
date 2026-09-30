# bipmatch

二分图匹配工具包，纯标准库，无外部依赖。

## 现状

`bipmatch/matcher.py` 提供 `NaiveMatcher`，只有一项能力：求最大匹配。

- `NaiveMatcher(left, right)`：左右各登记一批顶点名
- `add_left(name)` / `add_right(name)`：登记顶点，重复登记不改动已有结构
- `add_edge(left, right)`：登记一条边，未知顶点抛 `CannotMatchError`，
  自环抛 `SelfLoopError`，重边抛 `DuplicateEdgeError`
- `left_nodes()` / `right_nodes()` / `edges()` / `adjacency()`：查看已登记的图
- `match()`：返回最大匹配的边数
- `matching_edges()`：返回最大匹配的边集，按左侧登记顺序

求匹配的朴素做法是：左侧顶点逐个处理，每个左顶点跑一遍增广路暴力搜索，
深搜加逐点回溯找路径，找到就翻转配对，找不到就跳过；同一张图反复整题重搜，
直到某一轮没有任何增广为止。结果正确，但图一大、增广路一长就很慢。
它只报边数与边集：不提供最小顶点覆盖，不做匹配是否最大的判定，
也不记录搜索规模，也没有第二条独立算法可互相印证。

## 问题

只有一条朴素路径，规模一大就退化；没有最小顶点覆盖的构造；没有匹配是否最大的
独立判定；没有把搜索次数与分层规模暴露出来，慢在哪里无从对照。

## 目标

见任务描述。约束：

- `tests/test_matcher.py` 行为基线保持不变（基线一字不改且必须全绿）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 朴素最大匹配演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

（实现后补，10 行以内）
