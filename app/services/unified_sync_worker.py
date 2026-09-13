from __future__ import annotations

import threading

from app.services.live_unified_sync_builder import (
    build_live_unified_manager,
)


class UnifiedSyncWorker:

    def __init__(self) -> None:
        self.manager = build_live_unified_manager()
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

    def start(self):
        with self._lock:
            if (
                self._thread is not None
                and self._thread.is_alive()
            ):
                return self.manager.status()

            self._stop_event = threading.Event()

            self._thread = threading.Thread(
                target=self._run,
                name="dartsedge-unified-sync-worker",
                daemon=True,
            )
            self._thread.start()

            return self.manager.status()

    def stop(self):
        self._stop_event.set()
        self.manager.request_stop()

        thread = self._thread

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=10.0)

        return self.manager.status()

    def status(self):
        return self.manager.status()

    def run_once(self):
        return self.manager.run_cycle()

    def _run(self):
        try:
            while not self._stop_event.is_set():
                try:
                    self.manager.run_cycle()
                except Exception:
                    pass

                if self._stop_event.wait(
                    self.manager.poll_seconds
                ):
                    break
        finally:
            self.manager.close()


unified_sync_worker = UnifiedSyncWorker()
