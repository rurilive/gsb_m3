"""eventlog: 最朴素的事件日志基线。

目前只导出一个基线类 EventLog：一个只追加的全局事件列表。
多流、版本、快照、投影重建与订阅见任务描述。
"""

from eventlog.log import EventLog

__all__ = ["EventLog"]
