"""Round-robin, idle-priority search with cancellation and foreground precedence."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time

from .dataset import Dataset
from .evolution import SearchConfig
from .library import write_json
from .runner import ROOT


class BackgroundOptimizer:
    def __init__(self, library, *, enabled=True, interval=5, slice_seconds=4):
        self.library, self.enabled = library, enabled
        self.interval, self.slice_seconds = interval, slice_seconds
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._paused = False
        self._process = self._folder = self._task = None
        self._cursor = 0
        self._next_due = time.monotonic() + interval
        self._state = {"status": "idle" if enabled else "disabled", "attempts": 0,
                       "message": "Wartet auf den nächsten Durchgang." if enabled else "Deaktiviert."}

    def start(self):
        with self._lock:
            if self.enabled and self._thread is None and not self._stop.is_set():
                self._thread = threading.Thread(target=self._run, daemon=True, name="background-optimizer")
                self._thread.start()

    def status(self):
        with self._lock:
            return dict(self._state)

    def _discard(self):
        if self._process is not None:
            if self._process.poll() is None:
                self._process.terminate()
            self._process.wait(timeout=3)
        if self._folder is not None:
            self._folder.cleanup()
        self._process = self._folder = self._task = None

    def pause(self):
        with self._lock:
            self._paused = True
            self._discard()
            self._state.update(status="paused", message="Pausiert für eine manuelle Suche.", task_id=None)

    def resume(self):
        with self._lock:
            self._paused = False
            self._next_due = time.monotonic() + self.interval
            self._state.update(status="idle" if self.enabled else "disabled",
                               message="Wartet auf den nächsten Durchgang.", task_id=None)

    def cancel_task(self, task_id):
        with self._lock:
            if self._task and self._task["task_id"] == task_id:
                self._discard()
                self._next_due = time.monotonic() + self.interval
                self._state.update(status="idle", message="Suche für Frozen-Programm gestoppt.", task_id=None)

    def close(self):
        self._stop.set()
        with self._lock:
            self._discard()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=5)

    def _run(self):
        while not self._stop.wait(0.2):
            try:
                self.tick()
            except Exception as exc:
                with self._lock:
                    self._discard()
                    self._next_due = time.monotonic() + self.interval
                    self._state.update(status="error", message=str(exc), task_id=None)

    def tick(self):
        with self._lock:
            if not self.enabled or self._paused or self._stop.is_set():
                return
            now = time.monotonic()
            if self._process is not None:
                if self.library.is_frozen(self._task["task_id"]):
                    self.cancel_task(self._task["task_id"])
                    return
                code = self._process.poll()
                if code is None and now - self._started < self.slice_seconds:
                    return
                if code == 0:
                    result = json.loads((Path(self._folder.name) / "result.json").read_text(encoding="utf-8"))
                    dataset = Dataset.from_dict(self._task["dataset"])
                    selected = self.library.save_program(result, dataset, background=True)
                    improved = selected and selected.get("comparison", {}).get("accepted", False)
                    self._state.update(status="idle", message=(
                        f'{self._task["name"]}: bessere Version übernommen.' if improved
                        else f'{self._task["name"]}: bisherige Version bleibt.'))
                else:
                    message = "Zeitbudget erreicht." if code is None else "Suchdurchgang fehlgeschlagen."
                    error_log = Path(self._folder.name) / "error.log"
                    if code is not None and error_log.exists():
                        message += " " + error_log.read_text(encoding="utf-8", errors="replace")[-1000:].strip()
                    self._state.update(status="idle" if code is None else "error", message=message)
                self._discard()
                self._next_due = now + self.interval
                self._state["task_id"] = None
                return
            if now < self._next_due:
                return
            programs = sorted((p for p in self.library.programs() if not p["frozen"]), key=lambda p: p["task_id"])
            if not programs:
                self._state.update(status="idle", message="Keine Programme für die Hintergrundsuche.", task_id=None)
                self._next_due = now + self.interval
                return
            program = programs[self._cursor % len(programs)]
            self._cursor += 1
            dataset = self.library.load_dataset(program["dataset_id"])
            # Above 128 gates, attempt a smaller fresh circuit instead of truncating it.
            gates = min(128, max(8, program["fitness"]["gates"] + 2))
            config = SearchConfig(gates=gates, population=12, generations=100,
                                  seed=secrets.randbelow(2**31), backend="python",
                                  repair_cases=4, optimize=True)
            (ROOT / ".jobs").mkdir(exist_ok=True)
            self._folder = tempfile.TemporaryDirectory(dir=ROOT / ".jobs", prefix="background-")
            folder = Path(self._folder.name)
            self._task = {"task_id": program["task_id"], "name": program["dataset_name"],
                          "dataset": dataset.to_dict()}
            write_json(folder / "job.json", {"dataset": dataset.to_dict(), "config": asdict(config),
                                            "library": str(self.library.root.resolve())})
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT))
            flags = (subprocess.CREATE_NO_WINDOW | subprocess.IDLE_PRIORITY_CLASS) if os.name == "nt" else 0
            with (folder / "error.log").open("wb") as log:
                self._process = subprocess.Popen(
                    [sys.executable, "-m", "primitives.background_worker", str(folder / "job.json"), str(folder / "result.json")],
                    cwd=ROOT, env=env, creationflags=flags, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=log)
            self._started = now
            self._state.update(status="running", task_id=program["task_id"],
                               attempts=self._state["attempts"] + 1,
                               message=f'{program["dataset_name"]}: sucht mit niedriger Priorität …')
