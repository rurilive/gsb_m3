# indexly

纯标准库的内存文档检索小库，无外部依赖。

## 现状

indexly/docs.py 提供一个 LinearDocs：

- add、remove：按文档名加入或删除一篇文档，文档名重复报错、不存在报错
- doc_ids、text：按加入顺序取回文档名、按文档名取回原文
- search：唯一的检索入口，逐篇文档扫一遍，命中原文按词包含查询词的文档
- count：逐词统计某个词在所有文档原文里出现的总次数

检索只有整词扫描这一条路，大小写敏感，没有分词表、没有倒排表，没有
打分，没有多词布尔，也没有任何排序依据。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
