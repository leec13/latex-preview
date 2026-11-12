"""Exécution des calculs SymPy dans un processus séparé, interruptible.

L'interface ne se fige jamais : un calcul trop long est arrêté (délai) et le
processus relancé.
"""

from __future__ import annotations

import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from PySide6.QtCore import QObject, QTimer, Signal


class Runner(QObject):
    finished = Signal(int, dict)   # (numéro de requête, résultat)

    def __init__(self, warm_up=None, parent=None) -> None:
        super().__init__(parent)
        self._ctx = multiprocessing.get_context("spawn")
        self._warm_up = warm_up
        self._executor: ProcessPoolExecutor | None = None
        self._next_id = 0
        self._pending: dict[int, object] = {}
        self._start()

    def _start(self) -> None:
        self._executor = ProcessPoolExecutor(max_workers=1, mp_context=self._ctx)
        if self._warm_up is not None:
            self._executor.submit(self._warm_up)  # charge SymPy à l'avance

    @property
    def busy(self) -> bool:
        return bool(self._pending)

    def submit(self, fn, timeout_s: float = 20.0, **kwargs) -> int:
        self._next_id += 1
        rid = self._next_id
        try:
            fut = self._executor.submit(fn, **kwargs)
        except Exception:  # processus mort : on relance
            self.restart()
            fut = self._executor.submit(fn, **kwargs)
        self._pending[rid] = fut
        fut.add_done_callback(lambda f, rid=rid: self._done(rid, f))
        if timeout_s:
            QTimer.singleShot(int(timeout_s * 1000), lambda rid=rid: self._timeout(rid, timeout_s))
        return rid

    def _done(self, rid: int, fut) -> None:
        if self._pending.pop(rid, None) is None or fut.cancelled():
            return
        try:
            res = fut.result()
        except Exception as exc:
            res = {"ok": False, "error": f"Calcul interrompu ({type(exc).__name__})."}
        try:
            self.finished.emit(rid, res)
        except RuntimeError:  # application en cours de fermeture
            pass

    def _timeout(self, rid: int, timeout_s: float) -> None:
        if rid in self._pending:
            ids = list(self._pending)
            self._pending.clear()
            self.restart()
            for r in ids:
                self.finished.emit(r, {"ok": False, "error": f"Calcul interrompu : plus de {timeout_s:.0f} s."})

    def restart(self) -> None:
        self.shutdown()
        self._start()

    def shutdown(self) -> None:
        ex, self._executor = self._executor, None
        if ex is None:
            return
        for p in list(getattr(ex, "_processes", {}).values()):
            try:
                p.terminate()
            except Exception:
                pass
        ex.shutdown(wait=False, cancel_futures=True)
