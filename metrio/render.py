"""渲染层：Snapshot -> 三种导出格式。

字段顺序是下游契约（按字段序正则抓的），本层只做格式化，不算统计。
"""

import json
from typing import Any, Dict, List

from metrio.snapshot import Snapshot


def render_text(snapshot: Snapshot) -> str:
    lines: List[str] = []
    if len(snapshot.counters) > 0:
        lines.append("counters:")
        for c in snapshot.counters:
            lines.append("  %s = %d" % (c.name, c.value))
    if len(snapshot.histograms) > 0:
        lines.append("histograms:")
        for h in snapshot.histograms:
            lines.append(
                "  %s n=%d avg=%.2f min=%.2f max=%.2f p50=%.2f p95=%.2f"
                % (h.name, h.count, h.avg, h.min, h.max, h.p50, h.p95)
            )
    return "\n".join(lines)


def export_json(snapshot: Snapshot) -> str:
    # 字段顺序：name,count,sum,avg,min,max,p50,p95,p999（下游依赖）
    doc: Dict[str, Any] = {"counters": [], "histograms": []}
    for c in snapshot.counters:
        doc["counters"].append({"name": c.name, "value": c.value})
    for h in snapshot.histograms:
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


def export_prom(snapshot: Snapshot) -> str:
    # 字段顺序：quantile 行在前，_count/_sum 在后（下游依赖）
    out: List[str] = []
    for c in snapshot.counters:
        out.append("# TYPE %s counter" % c.name)
        out.append("%s %d" % (c.name, c.value))
    for h in snapshot.histograms:
        out.append("# TYPE %s summary" % h.name)
        if h.count > 0:
            out.append('%s{quantile="0.5"} %s' % (h.name, _g(float(h.p50))))
            out.append('%s{quantile="0.95"} %s' % (h.name, _g(float(h.p95))))
            out.append('%s{quantile="0.999"} %s' % (h.name, _g(float(h.p999))))
        out.append("%s_count %d" % (h.name, h.count))
        out.append("%s_sum %s" % (h.name, _g(h.sum)))
    return "\n".join(out)
