"""molib: 内存里的朴素离线区间查询工具。

当前只有逐项重扫的实现，见 molib/offline.py。每个区间查询都独立地
把区间从头扫一遍：不同值个数把元素收进集合再数大小，众数出现次数与
出现次数平方和先把区间内每个值的出现次数数出来再汇总。查询一多、
区间一长就白扫。莫队算法、指针增量维护与回滚处理见任务描述。
"""

from molib.offline import BadRange, BruteQueries, MoError

__all__ = ["BruteQueries", "MoError", "BadRange"]
