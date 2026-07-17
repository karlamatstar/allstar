"""Streamlit 대시보드의 K6·성능 시험 실행 상태를 서버 단위로 관리한다."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from allstar.shared.paths import PROJECT_ROOT
from allstar.shared.qa_reporting import QAReportSession


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090").rstrip("/")
K6_INSTALL_URL = "https://grafana.com/docs/k6/latest/set-up/install-k6/"
K6_MIN_VUS = 1
K6_MAX_VUS = 999
K6_MIN_DURATION = 10
K6_MAX_DURATION = 600


@dataclass(frozen=True)
class K6TestSpec:
    test_id: str
    title: str
    english: str
    description: str
    command_type: str
    command_target: str
    default_vus: int | None = None
    default_duration: int | None = None
    actual_api: bool = False
    write_summary_report: bool = False


K6_TEST_SPECS = (
    K6TestSpec(
        "ai_smoke", "기본 동작 시험", "Smoke Test",
        "가상 사용자 1명이 상태와 모의 채팅을 호출해 기본 연결과 HTTP 200 응답을 확인합니다.",
        "k6", "ops/performance/smoke_test.js",
    ),
    K6TestSpec(
        "ai_load", "일반 부하 시험", "Load Test",
        "일정한 일상 부하에서 응답 지연, 실패율과 처리 안정성을 확인합니다.",
        "k6", "ops/performance/load_test.js", 20, 60,
    ),
    K6TestSpec(
        "ai_random", "무작위 요청 시험", "Random Test",
        "가상 인원을 불규칙하게 바꾸며 예측하기 어려운 요청 증감에 대한 안정성을 확인합니다.",
        "k6", "ops/performance/random_test.js", 100, 60,
    ),
    K6TestSpec(
        "ai_stress", "한계 부하 시험", "Stress Test",
        "가상 인원을 단계적으로 늘려 처리 한계와 부하 감소 후 회복 여부를 확인합니다.",
        "k6", "ops/performance/stress_test.js", 100, 120,
    ),
    K6TestSpec(
        "ai_spike", "순간 급증 시험", "Spike Test",
        "가상 인원을 짧은 시간에 급격히 늘려 순간 폭주와 종료 후 복구 여부를 확인합니다.",
        "k6", "ops/performance/spike_test.js", 200, 60,
    ),
    K6TestSpec(
        "ai_validation", "장애·기능 검증 시험", "Validation Test",
        "지연·오류·시간 초과 장애를 재현하고 외부 AI 호출을 제외한 기능 회귀를 함께 검사합니다.",
        "python", "tools/scripts/run_validation_tests.py", write_summary_report=True,
    ),
    K6TestSpec(
        "ai_api_performance", "서버 연결 성능 종합 시험", "API Performance Test",
        "가상 사용자 1명·10명·25명이 실제 채팅 API를 단계별로 호출해 응답시간과 실패율을 확인합니다.",
        "python", "tools/scripts/run_performance_tests.py", actual_api=True, write_summary_report=True,
    ),
)
K6_TEST_SPEC_BY_ID = {spec.test_id: spec for spec in K6_TEST_SPECS}


def validate_load_settings(vus: int | str, duration: int | str) -> tuple[int, int]:
    try:
        parsed_vus = int(vus)
        parsed_duration = int(duration)
    except (TypeError, ValueError) as error:
        raise ValueError("가상 인원과 실행 시간은 숫자로 입력하세요.") from error
    return (
        min(K6_MAX_VUS, max(K6_MIN_VUS, parsed_vus)),
        min(K6_MAX_DURATION, max(K6_MIN_DURATION, parsed_duration)),
    )


def find_k6_executable() -> str | None:
    """현재 Streamlit 실행 환경과 같은 운영체제의 K6만 찾는다."""
    bundled_name = "k6.exe" if os.name == "nt" else "k6"
    bundled = PROJECT_ROOT / "RUN" / bundled_name
    if bundled.is_file():
        return str(bundled)
    return shutil.which("k6")


def read_k6_version(executable: str | None) -> tuple[bool, str]:
    if not executable:
        return False, "K6를 찾을 수 없음"
    try:
        completed = subprocess.run(
            [executable, "version"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=4,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"K6 실행 오류: {error}"
    output = (completed.stdout or completed.stderr or "").strip().splitlines()
    label = output[0] if output else Path(executable).name
    return completed.returncode == 0, label


def probe_http(url: str, expected_text: str | None = None) -> tuple[bool, str]:
    try:
        response = httpx.get(url, timeout=2.5)
    except httpx.HTTPError as error:
        return False, str(error)
    body = response.text.strip()
    ok = response.status_code == 200 and (expected_text is None or expected_text.lower() in body.lower())
    return ok, f"HTTP {response.status_code}" if ok else f"HTTP {response.status_code} · {body[:80]}"


def inspect_environment(portfolio_api: str, grafana_url: str) -> dict[str, dict[str, Any]]:
    executable = find_k6_executable()
    k6_ok, k6_detail = read_k6_version(executable)
    api_ok, api_detail = probe_http(f"{portfolio_api.rstrip('/')}/health")
    prometheus_ok, prometheus_detail = probe_http(f"{PROMETHEUS_URL}/-/ready", "ready")
    grafana_ok, grafana_detail = probe_http(f"{grafana_url.rstrip('/')}/api/health")
    return {
        "k6": {"ok": k6_ok, "detail": k6_detail, "executable": executable},
        "api": {"ok": api_ok, "detail": api_detail},
        "prometheus": {"ok": prometheus_ok, "detail": prometheus_detail},
        "grafana": {"ok": grafana_ok, "detail": grafana_detail},
        "required_ready": k6_ok and api_ok and prometheus_ok,
        "inside_docker": Path("/.dockerenv").exists(),
    }


def _target_host(portfolio_api: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(portfolio_api)
    if not parsed.hostname:
        return "127.0.0.1:8000"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return f"{parsed.hostname}:{port}"


def _build_command(spec: K6TestSpec, k6_executable: str) -> list[str]:
    target = str(PROJECT_ROOT / spec.command_target)
    if spec.command_type == "k6":
        return [k6_executable, "run", target]
    return [sys.executable, "-u", target]


@dataclass
class DashboardK6Run:
    spec: K6TestSpec
    report_session: QAReportSession
    process: subprocess.Popen
    command: list[str]
    settings: dict[str, Any]
    started_monotonic: float = field(default_factory=time.monotonic)
    cancel_requested: bool = False
    finalized: bool = False
    status: str = "running"
    exit_code: int | None = None
    result: dict[str, Any] | None = None

    @property
    def run_id(self) -> str:
        return self.report_session.run_id

    @property
    def log_path(self) -> Path:
        return self.report_session.log_path

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_monotonic)


_RUN_LOCK = threading.RLock()
_CURRENT_RUN: DashboardK6Run | None = None


def current_run() -> DashboardK6Run | None:
    with _RUN_LOCK:
        return _CURRENT_RUN


def _finish_run(run: DashboardK6Run) -> DashboardK6Run:
    if run.finalized:
        return run
    exit_code = run.process.poll()
    if exit_code is None:
        return run
    status = "cancelled" if run.cancel_requested else "completed" if exit_code == 0 else "failed"
    # 실패·중단 실행은 원문 로그와 이벤트만 남기고 기존 정상 최신 요약은 보호한다.
    if status != "completed":
        run.report_session.write_summary_report = False
    try:
        run.result = run.report_session.finish(status, exit_code)
    except Exception as error:
        run.report_session.append_output(f"\n[실행 결과 정리 실패] {error}\n")
        run.result = {"status": "report_failed", "error": str(error)}
        status = "failed"
    run.status = status
    run.exit_code = exit_code
    run.finalized = True
    return run


def poll_current_run() -> DashboardK6Run | None:
    with _RUN_LOCK:
        if _CURRENT_RUN is None:
            return None
        return _finish_run(_CURRENT_RUN)


def start_run(
    test_id: str,
    *,
    k6_executable: str,
    portfolio_api: str,
    vus: int | None = None,
    duration: int | None = None,
) -> DashboardK6Run:
    global _CURRENT_RUN
    with _RUN_LOCK:
        if _CURRENT_RUN is not None:
            _finish_run(_CURRENT_RUN)
            raise RuntimeError("진행 중이거나 확인하지 않은 이전 시험 결과가 있습니다.")
        spec = K6_TEST_SPEC_BY_ID[test_id]
        settings: dict[str, Any] = {"실행 위치": "통합 Streamlit 대시보드"}
        env = os.environ.copy()
        env.update({
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "TARGET_IP": _target_host(portfolio_api),
            "K6_PROMETHEUS_RW_SERVER_URL": f"{PROMETHEUS_URL}/api/v1/write",
            "K6_PROMETHEUS_RW_TREND_STATS": "p(95),p(99),avg,min,max",
        })
        if spec.default_vus is not None and spec.default_duration is not None:
            parsed_vus, parsed_duration = validate_load_settings(vus, duration)
            env["K6_VUS"] = str(parsed_vus)
            env["SCRIPT_DURATION"] = str(parsed_duration)
            settings.update({"최대 가상 인원(VU)": parsed_vus, "실행 시간(초)": parsed_duration})
        if spec.actual_api:
            settings.update({
                "실행 단계": "1명 → 10명 → 25명",
                "실행 방식": "단계별 독립 실행",
                "최대 실제 채팅 요청": 36,
            })
        command = _build_command(spec, k6_executable)
        report_session = QAReportSession(
            test_id=spec.test_id,
            test_name=f"{spec.title} ({spec.english})",
            command=command,
            settings=settings,
            write_summary_report=spec.write_summary_report,
        )
        env["K6_TEST_ID"] = report_session.run_id
        report_session.start()
        output_stream = report_session.log_path.open("a", encoding="utf-8")
        popen_options: dict[str, Any] = {
            "cwd": PROJECT_ROOT,
            "stdout": output_stream,
            "stderr": subprocess.STDOUT,
            "env": env,
            "creationflags": CREATE_NO_WINDOW,
        }
        if os.name != "nt":
            popen_options["start_new_session"] = True
        try:
            process = subprocess.Popen(report_session.command_for_execution(), **popen_options)
        except Exception as error:
            report_session.write_summary_report = False
            report_session.finish("start_failed", None, error=str(error))
            raise RuntimeError(f"시험 프로세스를 시작하지 못했습니다: {error}") from error
        finally:
            output_stream.close()
        _CURRENT_RUN = DashboardK6Run(spec, report_session, process, command, settings)
        return _CURRENT_RUN


def stop_current_run() -> bool:
    with _RUN_LOCK:
        run = _CURRENT_RUN
        if run is None or run.process.poll() is not None:
            return False
        run.cancel_requested = True
        run.report_session.append_output("\n[사용자 중지 요청] 실행 중인 시험과 하위 프로세스를 종료합니다.\n")
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(run.process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
        else:
            try:
                os.killpg(run.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        return True


def clear_finished_run() -> bool:
    global _CURRENT_RUN
    with _RUN_LOCK:
        if _CURRENT_RUN is None:
            return True
        _finish_run(_CURRENT_RUN)
        if not _CURRENT_RUN.finalized:
            return False
        _CURRENT_RUN = None
        return True


def reset_runner_for_tests() -> None:
    """격리된 자동 테스트에서만 서버 공통 실행 상태를 초기화한다."""
    global _CURRENT_RUN
    with _RUN_LOCK:
        _CURRENT_RUN = None
