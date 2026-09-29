# matchx

纯标准库的字符串检索工具，无外部依赖。

## 现状

`matchx/search.py` 提供朴素查找器 `NaiveSearch` 与一组便捷函数：

- `find(text, pat)`：返回首次出现的下标，未命中返回负一
- `find_all(text, pat)`：返回全部出现的起始下标（含重叠），升序
- `has(text, pat)`：是否出现过
- `count(text, pat)`：出现次数
- 空模式抛 `InvalidPatternError`（同时是 `MatchError` 与 `ValueError` 的子类）

内部每次查找都是双层逐位比对：从文本的每个位置起把模式逐字符对齐比较，
未命中就整体右移一位重来。

## 问题

双层比对在文本变长时会退化成平方级；多模式只能一个个模式分别扫；
没有可复用的前缀结构，也没有周期分析能力。

## 目标

见任务描述。约束：

- `tests/test_search.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 朴素查找演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

（实现后补，10 行以内）
