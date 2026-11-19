"""Roda funções lentas (checagens, varredura de pastas) fora da thread da interface."""
from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Bridge(QObject):
    done = Signal(object, object)  # result, error


class _Task(QRunnable):
    def __init__(self, fn, args):
        super().__init__()
        self.fn, self.args = fn, args
        self.bridge = _Bridge()

    def run(self):
        try:
            res = self.fn(*self.args)
            self.bridge.done.emit(res, None)
        except Exception as e:  # noqa: BLE001 - mostra o erro na UI em vez de derrubar o app
            traceback.print_exc()
            self.bridge.done.emit(None, e)


_alive: set = set()


def run_async(fn, *args, on_done=None):
    task = _Task(fn, args)
    _alive.add(task.bridge)

    def finish(res, err):
        _alive.discard(task.bridge)
        if on_done:
            on_done(res, err)

    task.bridge.done.connect(finish)
    task.setAutoDelete(True)
    QThreadPool.globalInstance().start(task)
