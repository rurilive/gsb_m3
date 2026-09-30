# coinchange

纯标准库的零钱兑换小工具，无外部依赖。

## 现状

`coinchange/core.py` 提供一份朴素实现 `NaiveCoinChange`：

- `__init__(coins, target)`：若干面值与目标金额，非法参数抛出 `CoinChangeError`
- `__len__()`：规范口径下的面值个数（升序、去重）
- `coins`：规范口径下的面值，升序且已去重
- `target`：目标金额
- `min_coins()`：递归枚举每一枚可用面值，逐个减目标价，返回最少硬币数
- `is_reachable()`：递归枚举判断目标金额是否可达
- `selection()`：给出一组达到最少硬币数的具体选法，按面值升序排列
- `count_min_ways()`：统计达到最少硬币数的方案个数
- `CoinChangeError`：参数错误的基类，继承 `Exception`

## 问题

`min_coins`、`is_reachable`、`selection`、`count_min_ways` 都是对目标金额做
逐枚面值的递归枚举，逐个减掉一枚硬币后继续往下递归，结果是正确的，但同一个
子目标会被反复重算，代价随目标金额指数级上涨。既没有按金额从小到大递推的一维
滚动数组动态规划主路径，也没有方案计数与可达性的口径区分，目标金额一大就撑不住。

## 目标

见任务描述。约束：

- `tests/test_core.py` 是基线，一字不许改且必须全绿
- 新行为另开 `tests/test_dp.py`
- 纯标准库，无第三方依赖

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
