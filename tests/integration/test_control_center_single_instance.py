from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

import pytest

from allstar.shared.single_instance import ERROR_ALREADY_EXISTS, SingleInstanceLock


ROOT = Path(__file__).resolve().parents[2]


class FakeKernel32:
    def __init__(self, last_error: int):
        self.last_error = last_error
        self.closed: list[int] = []

    def CreateMutexW(self, security, initial_owner, name):
        return 101

    def CloseHandle(self, handle):
        self.closed.append(handle)
        return True

    def get_last_error(self):
        return self.last_error


def test_single_instance_lock_keeps_and_releases_first_handle():
    kernel32 = FakeKernel32(0)
    lock = SingleInstanceLock("Local\\AllStarTest", kernel32=kernel32)

    assert lock.acquire() is True
    assert kernel32.closed == []

    lock.release()
    assert kernel32.closed == [101]


def test_single_instance_lock_closes_duplicate_handle_immediately():
    kernel32 = FakeKernel32(ERROR_ALREADY_EXISTS)
    lock = SingleInstanceLock("Local\\AllStarTest", kernel32=kernel32)

    assert lock.acquire() is False
    assert kernel32.closed == [101]


@pytest.mark.skipif(os.name != "nt", reason="Windows 이름 있는 뮤텍스 검증")
def test_single_instance_lock_blocks_another_process():
    mutex_name = f"Local\\AllStarSingleInstanceTest{os.getpid()}"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    holder_code = (
        "from allstar.shared.single_instance import SingleInstanceLock;"
        f"lock=SingleInstanceLock({mutex_name!r});"
        "print('ready' if lock.acquire() else 'duplicate', flush=True);"
        "input();lock.release()"
    )
    probe_code = (
        "from allstar.shared.single_instance import SingleInstanceLock;"
        f"lock=SingleInstanceLock({mutex_name!r});"
        "print('acquired' if lock.acquire() else 'duplicate', flush=True);"
        "lock.release()"
    )
    holder = subprocess.Popen(
        [sys.executable, "-u", "-c", holder_code],
        cwd=ROOT,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "ready"
        probe = subprocess.run(
            [sys.executable, "-u", "-c", probe_code],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        assert probe.stdout.strip() == "duplicate"
    finally:
        if holder.stdin:
            holder.stdin.write("\n")
            holder.stdin.flush()
        holder.wait(timeout=10)


def test_both_control_centers_show_warning_and_server_guard_skips_cleanup():
    server_main = (ROOT / "tools" / "server_control" / "main.py").read_text(encoding="utf-8")
    qa_main = (ROOT / "tools" / "qa_control" / "main.py").read_text(encoding="utf-8")
    guard = (ROOT / "tools" / "server_control" / "shutdown_guard.py").read_text(encoding="utf-8")

    assert 'SingleInstanceLock("Local\\\\AllStarServerControlCenter")' in server_main
    assert 'SingleInstanceLock("Local\\\\AllStarQAControlCenter")' in qa_main
    assert server_main.count('messagebox.showwarning("이미 실행 중입니다"') == 1
    assert qa_main.count('messagebox.showwarning("이미 실행 중입니다"') == 1
    assert "exit_code == DUPLICATE_INSTANCE_EXIT_CODE" in guard
    duplicate_branch = guard.split("exit_code == DUPLICATE_INSTANCE_EXIT_CODE", 1)[1].split("elif clean_marker.exists()", 1)[0]
    assert "stop_project_services" not in duplicate_branch
