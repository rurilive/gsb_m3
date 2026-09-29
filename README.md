# coinlib

一个纯标准库的钱包库，无外部依赖。记账、报销、分销结算这类场景都要把一笔钱
算准，coinlib 就是干这件事的那一层。

## 现状

- `coinlib/wallet.py`：`Wallet` 用一个浮点数存余额，`deposit` 与 `withdraw`
  就是浮点数的直接加减，`balance` 把当前浮点余额返回。
- `coinlib/__init__.py`：只导出基线类 `Wallet`。
- 金额是裸浮点数，没有货币概念，也没有任何精度处理。

现有实现没有货币代码，跨币种的钱混在一起也拦不住；金额是浮点，几次加减之后
边界上会出现尾差；一笔钱要按权重拆给多方，只能自己浮点除，各方之和经常与原额
差一分；金额想格式化成带货币的字符串，或者从字符串解析回来，都没有落脚点。
改造前的基线行为锁在 `tests/test_wallet.py`，改造后这个文件一字不改且必须全绿。

## 目标（见任务描述）

见任务描述。约束：

- 现有行为与 `tests/test_wallet.py` 基线一致（基线一个字不改）
- 新行为另开 `tests/test_money.py`，用逐字断言的边界值
- 纯标准库，Python 3.10 以上，不引第三方
- 全程用最小单位整数或 Decimal，不得出现浮点误差
- 可诊断错误一律继承 `MoneyError` 基类

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
