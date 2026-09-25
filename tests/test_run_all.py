"""
The multi-process launcher.

Root-level because `run_all.py` belongs to neither bot -- and deliberately so:
this suite must not import `admin_bot` or `user_bot`, whose shared `app.*`
package name makes them uncollectable in the same pytest process.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import run_all  # noqa: E402


def test_every_service_entrypoint_exists():
    """Catches an entrypoint being renamed or moved out from under the launcher."""
    for label, cwd, argv in run_all.SERVICES:
        script = cwd / argv[-1]
        assert script.is_file(), f"{label} points at a missing script: {script}"


def test_all_three_processes_are_covered():
    labels = {label for label, _, _ in run_all.SERVICES}
    assert labels == {"admin_bot", "user_bot", "webhook"}


def test_services_run_as_separate_interpreters():
    """
    Each service must be its own process.

    Both bots name their internal package `app`, so running them in one
    interpreter makes `import app...` resolve ambiguously. Separate
    interpreters make that impossible rather than merely unlikely.
    """
    for _label, _cwd, argv in run_all.SERVICES:
        assert argv[0] == sys.executable


def _run_launcher(tmp_path: Path, child_body: str, timeout: float = 20.0):
    """Run run_all.py against throwaway child scripts instead of the real bots."""
    script = tmp_path / "child.py"
    script.write_text(textwrap.dedent(child_body), encoding="utf-8")

    harness = tmp_path / "harness.py"
    harness.write_text(
        textwrap.dedent(
            f"""
            import sys
            from pathlib import Path
            sys.path.insert(0, {str(REPO_ROOT)!r})
            import run_all

            run_all.SERVICES = [
                ("a", Path({str(tmp_path)!r}), [sys.executable, "child.py"]),
                ("b", Path({str(tmp_path)!r}), [sys.executable, "child.py"]),
            ]
            sys.exit(run_all.main())
            """
        ),
        encoding="utf-8",
    )
    return subprocess.run(
        [sys.executable, str(harness)], capture_output=True, text=True, timeout=timeout
    )


def test_one_child_exiting_brings_the_group_down(tmp_path):
    """
    A half-running deployment is worse than a stopped one: a dead webhook
    silently drops payments, which is far harder to notice than nothing
    running at all.
    """
    result = _run_launcher(
        tmp_path,
        """
        import sys, time
        # First process to start exits immediately; the other would idle forever.
        marker = sys.argv[0] + ".started"
        import os
        if os.path.exists(marker):
            time.sleep(30)
        else:
            open(marker, "w").close()
            sys.exit(3)
        """,
    )
    assert result.returncode != 0
    assert "stopping the rest" in result.stdout
    assert "stopped" in result.stdout


def test_missing_entrypoint_fails_fast(tmp_path):
    harness = tmp_path / "harness.py"
    harness.write_text(
        textwrap.dedent(
            f"""
            import sys
            from pathlib import Path
            sys.path.insert(0, {str(REPO_ROOT)!r})
            import run_all

            run_all.SERVICES = [("ghost", Path({str(tmp_path)!r}), [sys.executable, "nope.py"])]
            sys.exit(run_all.main())
            """
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(harness)], capture_output=True, text=True, timeout=20
    )
    assert result.returncode == 1
    assert "cannot find entrypoints" in result.stdout
    assert "ghost" in result.stdout
