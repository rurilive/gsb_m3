"""渲染层：Snapshot → 文本/JSON/prom 字节级稳定输出。

三种导出共享同一份快照（见 snapshot.py），不再各自排序、算分位、拼字段；
格式差异（字段顺序、%.2f vs %g）只留在各自的渲染函数里。
"""

import json

from metrio.snapshot import Snapshot


def render_text(snap: Snapshot) -> str:
    """人看的文本导出。空注册表返回空串。"""

    lines: list[str] = []
    if snap.counters:
        lines.append("counters:")
        for c in snap.counters:
            lines.append("  %s = %d" % (c.name, c.value))
    if snap.histograms:
        lines.append("histograms:")
        for h in snap.histograms:
            lines.append(
                "  %s n=%d avg=%.2f min=%.2f max=%.2f p50=%.2f p95=%.2f"
                % (h.name, h.count, h.avg, h.min, h.max, h.p50, h.p95)
            )
    return "\n".join(lines)


def export_json(snap: Snapshot) -> str:
    """JSON 导出。字段顺序：name,count,sum,avg,min,max,p50,p95,p999（下游依赖）。"""

    doc = {"counters": [], "histograms": []}
    for c in snap.counters:
        doc["counters"].append({"name": c.name, "value": c.value})
    for h in snap.histograms:
        doc["histograms"].append(
            {
                "name": h.name,
                "count": h.count,
                "sum": h.sum,
                "avg": h.avg,
                "min": h.min,
                "max": h.max,
                "p50": h.p50,
                "p95": h.p95,
                "p999": h.p999,
            }
        )
    return json.dumps(doc)


def _g(v: float) -> str:
    # prom 风格的数字（%g），和 text/json 的 %.2f 不是一套（历史如此）
    return "%g" % v


def export_prom(snap: Snapshot) -> str:
    """prom 风格导出。字段顺序：quantile 行在前，_count/_sum 在后（下游依赖）。"""

    out: list[str] = []
    for c in snap.counters:
        out.append("# TYPE %s counter" % c.name)
        out.append("%s %d" % (c.name, c.value))
    for h in snap.histograms:
        out.append("# TYPE %s summary" % h.name)
        if h.count > 0:
            out.append('%s{quantile="0.5"} %s' % (h.name, _g(float(h.p50))))
            out.append('%s{quantile="0.95"} %s' % (h.name, _g(float(h.p95))))
            out.append('%s{quantile="0.999"} %s' % (h.name, _g(float(h.p999))))
        out.append("%s_count %d" % (h.name, h.count))
        out.append("%s_sum %s" % (h.name, _g(h.sum)))
    return "\n".join(out)
