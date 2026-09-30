"""lichaotree: 直线集合的在线最值工具。

当前只有改造前的朴素实现，见 lichaotree/lines.py。它内部只留一个直线列表，
每问一次某横坐标的最值就把已插入的全部直线逐条求值，每问一次区间最小值
就把区间内每个整数横坐标逐个点名、每个点再逐条求值；没有按定义域建的树，
没有中点比较，也没有区间合并或批量共享。

升级到李超线段树、另起一条逐条求值的独立路径、边界与确定性，见任务描述。
"""

from lichaotree.lines import (
    Erro,
    IllegalArgument,
    Line,
    NaiveLines,
)

__all__ = [
    "Erro",
    "IllegalArgument",
    "Line",
    "NaiveLines",
]
