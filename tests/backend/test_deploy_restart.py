"""Tests for the PID-file restart mechanism in scripts/deploy.sh."""

import os
import signal
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def pid_dir(tmp_path):
    """Provide a temporary directory for PID and log files."""
    return tmp_path


def _start_dummy(pid_file: Path) -> subprocess.Popen:
    """Start a long-running dummy process and record its PID."""
    proc = subprocess.Popen(
        ["sleep", "300"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pid_file.write_text(str(proc.pid))
    return proc


def _process_exited(proc: subprocess.Popen) -> bool:
    """Check whether a Popen process has exited (reaping zombies)."""
    return proc.poll() is not None


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _restart_script(pid_file: Path, log_file: Path) -> str:
    """Return a shell snippet that performs the same restart logic as deploy.sh.

    This extracts the restart portion of scripts/deploy.sh so we can test it
    in isolation without needing the full pipeline, venv, or uvicorn.
    Instead of starting uvicorn, it starts a ``sleep 300`` dummy process.
    """
    return textwrap.dedent(f"""\
        #!/usr/bin/env bash
        set -e

        PID_FILE="{pid_file}"
        LOG_FILE="{log_file}"

        # Stop existing server if running.
        if [ -f "$PID_FILE" ]; then
            OLD_PID=$(cat "$PID_FILE")
            if kill -0 "$OLD_PID" 2>/dev/null; then
                kill "$OLD_PID"
                for _ in 1 2 3 4 5; do
                    kill -0 "$OLD_PID" 2>/dev/null || break
                    sleep 0.2
                done
                if kill -0 "$OLD_PID" 2>/dev/null; then
                    kill -9 "$OLD_PID"
                fi
            fi
            rm -f "$PID_FILE"
        fi

        # Start a dummy process in place of uvicorn.
        nohup sleep 300 > "$LOG_FILE" 2>&1 &
        NEW_PID=$!
        echo "$NEW_PID" > "$PID_FILE"
    """)


class TestDeployRestart:
    def test_kills_existing_process_via_pid_file(self, pid_dir):
        """The restart logic should terminate the process whose PID is on file."""
        pid_file = pid_dir / "uvicorn.pid"
        log_file = pid_dir / "uvicorn.log"
        old_proc = _start_dummy(pid_file)
        old_pid = old_proc.pid

        assert old_proc.poll() is None, "Dummy process should be running"

        script = _restart_script(pid_file, log_file)
        result = subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Reap the zombie and verify the old process has exited.
        time.sleep(0.5)
        assert _process_exited(old_proc), "Old process should have been killed"

        # A new PID should be written.
        assert pid_file.exists()
        new_pid = int(pid_file.read_text().strip())
        assert new_pid != old_pid
        assert _is_running(new_pid), "New process should be running"

        # Clean up.
        os.kill(new_pid, signal.SIGKILL)

    def test_starts_fresh_when_no_pid_file(self, pid_dir):
        """When no PID file exists, the script should start a new process."""
        pid_file = pid_dir / "uvicorn.pid"
        log_file = pid_dir / "uvicorn.log"

        assert not pid_file.exists()

        script = _restart_script(pid_file, log_file)
        result = subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        assert pid_file.exists()
        new_pid = int(pid_file.read_text().strip())
        assert _is_running(new_pid), "New process should be running"

        # Clean up.
        os.kill(new_pid, signal.SIGKILL)

    def test_handles_stale_pid_file(self, pid_dir):
        """When the PID file references a dead process, the script should
        clean up and start a new one without error."""
        pid_file = pid_dir / "uvicorn.pid"
        log_file = pid_dir / "uvicorn.log"

        # Write a PID that doesn't correspond to any running process.
        # PID 2^22 is almost certainly unused.
        pid_file.write_text("4194304")

        script = _restart_script(pid_file, log_file)
        result = subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        assert pid_file.exists()
        new_pid = int(pid_file.read_text().strip())
        assert _is_running(new_pid), "New process should be running"

        # Clean up.
        os.kill(new_pid, signal.SIGKILL)

    def test_deploy_script_exists_and_is_executable(self):
        """scripts/deploy.sh should exist and contain the restart logic."""
        deploy_sh = REPO_ROOT / "scripts" / "deploy.sh"
        assert deploy_sh.exists(), "scripts/deploy.sh should exist"

        content = deploy_sh.read_text()
        assert "PID_FILE=" in content, "deploy.sh should define PID_FILE"
        assert "kill" in content, "deploy.sh should kill the old process"
        assert "nohup uvicorn" in content, "deploy.sh should start uvicorn in background"
        assert "api/health" in content, "deploy.sh should verify server health"
        assert "placeholder" not in content.lower(), "deploy.sh should not contain placeholder text"
