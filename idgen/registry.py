"""实例号注册表：用共享目录上的租约文件尽早发现实例号写重。"""
import json
import os
import socket
import time

DEFAULT_TTL_SECONDS = 30


class DuplicateInstanceError(RuntimeError):
    """同一实例号已被存活实例占用时抛出。"""


class _Lease:
    def __init__(self, registry, instance_id):
        self._registry = registry
        self._instance_id = instance_id
        self._released = False

    def heartbeat(self):
        if self._released:
            raise RuntimeError("租约已释放")
        self._registry._write(self._instance_id)

    def release(self):
        if not self._released:
            self._released = True
            self._registry._remove(self._instance_id)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.release()


class FileInstanceRegistry:
    """把租约目录放到各机房共享的存储上，即可跨机器检测实例号冲突。"""

    def __init__(self, directory, ttl_seconds=DEFAULT_TTL_SECONDS,
                 clock=time.time):
        self._directory = directory
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        os.makedirs(directory, exist_ok=True)

    def _path(self, instance_id):
        return os.path.join(self._directory, "instance-%d.lease" % instance_id)

    def _write(self, instance_id):
        payload = {
            "instance_id": instance_id,
            "owner": "%s:%d" % (socket.gethostname(), os.getpid()),
            "expires_at": self._clock() + self._ttl_seconds,
        }
        tmp = self._path(instance_id) + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(payload, fh)
        os.replace(tmp, self._path(instance_id))

    def _remove(self, instance_id):
        try:
            os.unlink(self._path(instance_id))
        except FileNotFoundError:
            pass

    def claim(self, instance_id):
        try:
            fd = os.open(self._path(instance_id),
                         os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            with open(self._path(instance_id)) as fh:
                payload = json.load(fh)
            if payload.get("expires_at", 0) > self._clock():
                raise DuplicateInstanceError(
                    "实例号 %d 已被 %s 占用"
                    % (instance_id, payload.get("owner")))
            self._remove(instance_id)
            return self.claim(instance_id)
        self._write(instance_id)
        return _Lease(self, instance_id)
