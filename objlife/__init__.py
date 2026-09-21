"""objlife：带销毁回调的引用计数对象容器。

create / retain / release 管外部引用，link / unlink 管对象之间的强引用，
计数归零当场回收并回调。walk 里是从一组根出发的只读遍历。
"""

from objlife.errors import LinkError, RefCountError, StoreError, UnknownObject
from objlife.store import ObjectStore
from objlife.walk import layers, reachable

__all__ = [
    "ObjectStore",
    "StoreError",
    "UnknownObject",
    "RefCountError",
    "LinkError",
    "reachable",
    "layers",
]
