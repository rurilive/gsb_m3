"""metrio.meters：进程内计数器/直方图收集与文本导出。

重构后状态全部收在 :class:`~metrio.registry.Registry` 实例里；本模块只保留
全进程共享的默认实例和对外薄壳函数（签名/返回值不变）。导出走
"快照 → 渲染"管线：统计口径见 metrio.snapshot，格式渲染见 metrio.renderers。
"""

from metrio.registry import Registry
from metrio.renderers import export_json as _export_json
from metrio.renderers import export_prom as _export_prom
from metrio.renderers import render_text as _render_text

# 全进程共享的默认注册表（保持模块级名字 REGISTRY 可导入，历史兼容）。
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


def observe(name: str, value: float) -> None:
    """往直方图里记一个样本。没注册过会顺手注册（历史行为）。"""

    REGISTRY.observe(name, value)


def render_text() -> str:
    """人看的文本导出。空注册表返回空串。"""

    return _render_text(REGISTRY.snapshot())


def export_json() -> str:
    """JSON 导出。字段顺序：name,count,sum,avg,min,max,p50,p95,p999（下游依赖）。"""

    return _export_json(REGISTRY.snapshot())


def export_prom() -> str:
    """prom 风格导出。字段顺序：quantile 行在前，_count/_sum 在后（下游依赖）。"""

    return _export_prom(REGISTRY.snapshot())


def reset() -> None:
    """清空全部指标（进程内测试用）。"""

    REGISTRY.reset()
