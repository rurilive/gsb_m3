"""leasekit: 调度器里管分片租约的进程内小包。"""

from .lease import Lease, LeaseManager

__all__ = ["Lease", "LeaseManager"]
