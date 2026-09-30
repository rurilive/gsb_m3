# palx

回文子串相关问题的朴素工具，纯标准库，无外部依赖。

## 现状

palx/strings.py 提供 PalindromeTools：

- PalindromeTools(text="")：收下一条文本，非字符串立刻报错
- text()：取回文本本身
- is_palindrome(start, end)：判断文本中 [start, end) 子串是否回文
- count_palindromes()：统计回文子串（含重复出现）的总个数
- longest_palindrome()：最长回文子串，取最早出现的一例
- min_palindrome_cut()：最小回文划分的段数
- count_palindrome_cut()：回文划分的方案总数
- expand_steps()：最近一次求最长回文时中心扩展的比较次数

内部判断回文一律把子串切片再反转后整体比较；求最长回文对每个中心向两边逐字符
扩展；统计回文个数、求最小回文划分与划分计数都是先枚举出全部子串，再逐个判断
是否回文，规模一大就是平方或立方级。结果正确，速度不快，也没有任何可复用的
回文半径。

## 问题

每判一次回文就要切片反转再逐字符比，字符重复度高时退化明显；统计回文个数、
求最长回文、求最小回文划分都把全部子串枚举出来再逐个判断，长文本下代价随长度
平方甚至立方增长；两条路径之间没有一套可以常数级判定任意子串回文、并能顺带
给出回文个数的回文半径机制可比。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_palindrome.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
