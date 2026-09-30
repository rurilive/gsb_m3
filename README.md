# unionfind

并查集与动态连通性的朴素实现，纯标准库，无外部依赖。

## 现状

`unionfind/core.py` 提供 `UnionFind`：

- `add(x)`：登记元素，幂等
- `elements()`、`contains(x)`：已登记元素与是否登记
- `find(x)`：所在集合的根，逐个集合、逐个成员线性扫描
- `connected(a, b)`：两点是否连通，同一点恒连通
- `size(x)`、`rank(x)`：集合大小与高度
- `group_members(x)`、`groups()`、`component_count()`、`component_sizes()`：集合成员与整体统计
- `union(a, b)`：把 b 集合的成员逐个搬进 a 集合，真正合并才返回真
- `union_weighted(a, b, w)`：建立关系，令 a 相对 b 的偏移恰为 w
- `relate(a, b)`：a 相对 b 的偏移，不同集合抛 `NotConnected`
- `undo()`、`rollback_to(t)`、`history_len()`、`connected_at(t, a, b)`：回滚与历史查询
- `count_moves()`、`count_visits()`、`cost_report()`：搬移与扫描的规模计数

现状全部走朴素口径：合并把一侧成员逐个搬进另一侧，查询逐元素线性扫，带权偏移逐元素
重算，回滚靠每次合并前整份状态深拷贝。口径直白、结果确定，但合并与查询一多就退化到
平方量级，内存也随合并次数线性膨胀。异常基类是 `UnionFindError`，输入不合法抛
`UnionFindInputError`，查询未登记元素抛 `UnknownNode`，越界回滚抛 `IllegalRollback`。

## 问题

没有路径压缩与按秩或按大小合并，连通查询与集合合并拿不到近常数级的均摊代价；带权
关系只靠逐元素重算偏移，缺少压缩路径时同步累加的维护方式；回滚靠整份状态深拷贝，
既占内存又慢，拿不到真正可撤销的合并栈；也没有把朴素搬移次数与压缩合并访问次数做
规模对照，优劣无法量化。

## 目标

见任务描述。约束：

- `tests/test_core.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件，基线路径不许删除
- 纯标准库

## 运行

```bash
python3 demo.py                          # 朴素搬移演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

（实现后补，10 行以内）
