"""写优先的读写锁，条件变量实现。"""

import threading
from contextlib import contextmanager


class RWLock:
    """写者优先的读写锁。

    读者可以同时进；已经有写者在排队时，新来的读者也要排队，
    免得写者被源源不断的读饿死。
    """

    def __init__(self):
        self._cond = threading.Condition()
        self._readers = 0
        self._writing = False
        self._waiting_writers = 0

    def acquire_read(self):
        with self._cond:
            while self._writing or self._waiting_writers > 0:
                self._cond.wait()
            self._readers += 1

    def release_read(self):
        with self._cond:
            if self._readers > 0:
                self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()

    def acquire_write(self):
        with self._cond:
            self._waiting_writers += 1
            try:
                while self._writing or self._readers > 0:
                    self._cond.wait()
                self._writing = True
            finally:
                self._waiting_writers -= 1

    def release_write(self):
        with self._cond:
            self._writing = False
            self._cond.notify_all()

    @contextmanager
    def read(self):
        self.acquire_read()
        try:
            yield self
        finally:
            self.release_read()

    @contextmanager
    def write(self):
        self.acquire_write()
        try:
            yield self
        finally:
            self.release_write()

    def reader_count(self):
        """当前持有读锁的线程数，观测用。"""
        with self._cond:
            return self._readers
