"""metrio.meters：进程内计数器/直方图收集与文本导出。

状态收在 Registry 实例里（metrio.registry），本模块的函数只是默认实例
REGISTRY 的薄壳转发；导出走 快照 -> 渲染 管线（metrio.snapshot /
metrio.render）。导出格式是稳定契约，下游按字段顺序在抓，别动输出。
"""

from metrio import render as _render
from metrio.registry import Registry
from metrio.snapshot import Number

# 进程默认的注册表实例；模块级函数都转发到它。名字保留是为了兼容旧的
# `from metrio import REGISTRY`，但它不再是裸 dict，别当下标用。
REGISTRY = Registry()


def inc(name: str, n: int = 1) -> int:
    """计数器加 n。n 允许负数（历史行为：不拦）。返回加完的值。"""
    return REGISTRY.inc(name, n)


def counter_value(name: str, default: int = 0) -> int:
    """读计数器当前值，没注册过返回 default。"""
    return REGISTRY.counter_value(name, default)


def histogram(name: str) -> None:
    """注册一个空直方图（后面 observe 往里灌样本）。"""
    REGISTRY.histogram(name)


def observe(name: str, value: Number) -> None:
    """往直方图里记一个样本。没注册过会顺手注册（历史行为）。"""
    REGISTRY.observe(name, value)


def render_text() -> str:
    """人看的文本导出。空注册表返回空串。"""
    return _render.render_text(REGISTRY.snapshot())


def export_json() -> str:
    """JSON 导出。字段顺序：name,count,sum,avg,min,max,p50,p95,p999（下游依赖）。"""
    return _render.export_json(REGISTRY.snapshot())


def export_prom() -> str:
    """prom 风格导出。字段顺序：quantile 行在前，_count/_sum 在后（下游依赖）。"""
    return _render.export_prom(REGISTRY.snapshot())


def reset() -> None:
    """清空全部指标（进程内测试用）。"""
    REGISTRY.reset()
