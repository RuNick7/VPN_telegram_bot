#!/usr/bin/env python3
"""
Start every bot process from one file.

    python run_all.py

Runs admin_bot, user_bot (polling), and the YooKassa webhook server together,
supervises them, and shuts all three down cleanly on Ctrl-C or SIGTERM.

**These are child processes, not threads or tasks in one interpreter.** Both
bots name their internal package `app`, so importing them into a single
process makes `import app.config.settings` resolve to whichever happened to
land on `sys.path` first. Separate interpreters keep that ambiguity impossible
rather than merely unlikely. (Removing that constraint means renaming one
bot's package -- worth doing eventually, not a prerequisite for this.)

A child that exits brings the whole group down instead of limping along
half-running: a stopped webhook silently drops payments, and noticing that
from the outside is much harder than noticing that nothing is running.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

# (label, working directory, argv) -- each runs the same entrypoint a human
# would run by hand, so there is no second code path to keep in sync.
SERVICES: list[tuple[str, Path, list[str]]] = [
    ("admin_bot", REPO_ROOT / "admin_bot", [sys.executable, "main.py"]),
    ("user_bot", REPO_ROOT / "user_bot", [sys.executable, "bot.py"]),
    ("webhook", REPO_ROOT / "user_bot", [sys.executable, "run_webhook.py"]),
]

# How long a child gets to exit on its own after SIGTERM before it is killed.
SHUTDOWN_GRACE_SECONDS = 10.0
POLL_INTERVAL_SECONDS = 0.5


def log(message: str) -> None:
    print(f"[run_all] {message}", flush=True)


def start(label: str, cwd: Path, argv: list[str]) -> subprocess.Popen:
    log(f"starting {label}: {' '.join(argv)} (cwd={cwd})")
    # PYTHONUNBUFFERED keeps child logs interleaved in real time rather than
    # appearing in blocks whenever their pipe buffer fills.
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    return subprocess.Popen(argv, cwd=str(cwd), env=env)


def stop_all(children: dict[str, subprocess.Popen]) -> None:
    """SIGTERM everything, then SIGKILL whatever is still alive."""
    alive = {label: proc for label, proc in children.items() if proc.poll() is None}
    for label, proc in alive.items():
        log(f"stopping {label} (pid {proc.pid})")
        try:
            proc.terminate()
        except OSError:
            pass

    deadline = time.monotonic() + SHUTDOWN_GRACE_SECONDS
    while time.monotonic() < deadline:
        if all(proc.poll() is not None for proc in alive.values()):
            return
        time.sleep(POLL_INTERVAL_SECONDS)

    for label, proc in alive.items():
        if proc.poll() is None:
            log(f"{label} did not stop in {SHUTDOWN_GRACE_SECONDS:.0f}s; killing")
            try:
                proc.kill()
            except OSError:
                pass


def main() -> int:
    missing = [label for label, cwd, argv in SERVICES if not (cwd / argv[-1]).exists()]
    if missing:
        log(f"cannot find entrypoints for: {', '.join(missing)}")
        return 1

    children: dict[str, subprocess.Popen] = {}
    shutting_down = False

    def handle_signal(signum, _frame):
        nonlocal shutting_down
        if not shutting_down:
            shutting_down = True
            log(f"received signal {signum}; shutting down")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        for label, cwd, argv in SERVICES:
            children[label] = start(label, cwd, argv)

        log(f"all {len(children)} processes started; Ctrl-C to stop")

        exit_code = 0
        while not shutting_down:
            for label, proc in children.items():
                code = proc.poll()
                if code is not None:
                    log(f"{label} exited with code {code}; stopping the rest")
                    exit_code = code or 1
                    shutting_down = True
                    break
            if not shutting_down:
                time.sleep(POLL_INTERVAL_SECONDS)
        return exit_code
    finally:
        stop_all(children)
        log("stopped")


if __name__ == "__main__":
    sys.exit(main())
