"""AllStar 운영 안정성 검증 도구.

외부 AI API를 사용하지 않는 상태 점검, 장시간 모의 요청, 동시 사용자,
Compose 재시작 및 프로젝트 내부 네트워크 변동을 재현하고 결과를 저장한다.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import httpx


ROOT = Path(__file__).resolve().parents[2]
LOG_ROOT = ROOT / "_OUTPUT" / "logs" / "services" / "operational_stability"
REPORT_ROOT = ROOT / "_OUTPUT" / "reports" / "operations"

HTTP_SERVICES = {
    "ai_api": "http://127.0.0.1:8000/health",
    "voc_api": "http://127.0.0.1:8100/health",
    "prometheus": "http://127.0.0.1:9090/-/ready",
    "grafana": "http://127.0.0.1:3000/api/health",
}
TCP_SERVICES = {f"voc_agent_{port}": ("127.0.0.1", port) for port in range(6001, 6007)}
CHAT_MOCK_URL = "http://127.0.0.1:8000/chat_mock"
VOC_AGENTS_HEALTH_URL = "http://127.0.0.1:8100/agents/health"


@dataclass(frozen=True)
class Probe:
    service: str
    ok: bool
    latency_ms: float
    detail: str


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * ratio) - 1))
    return round(ordered[index], 2)


def _http_probe(name: str, url: str, timeout: float = 3.0) -> Probe:
    started = time.perf_counter()
    try:
        response = httpx.get(url, timeout=timeout)
        elapsed = (time.perf_counter() - started) * 1000
        ok = 200 <= response.status_code < 400
        return Probe(name, ok, round(elapsed, 2), f"HTTP {response.status_code}")
    except httpx.HTTPError as error:
        elapsed = (time.perf_counter() - started) * 1000
        return Probe(name, False, round(elapsed, 2), f"{type(error).__name__}: {error}")


def _tcp_probe(name: str, host: str, port: int, timeout: float = 1.0) -> Probe:
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            elapsed = (time.perf_counter() - started) * 1000
            return Probe(name, True, round(elapsed, 2), f"TCP {host}:{port}")
    except OSError as error:
        elapsed = (time.perf_counter() - started) * 1000
        return Probe(name, False, round(elapsed, 2), f"{type(error).__name__}: {error}")


def probe_all() -> list[Probe]:
    tasks: list[tuple[Callable[..., Probe], tuple[Any, ...]]] = [
        (_http_probe, (name, url)) for name, url in HTTP_SERVICES.items()
    ]
    tasks.extend(
        (_tcp_probe, (name, host, port))
        for name, (host, port) in TCP_SERVICES.items()
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = [executor.submit(function, *arguments) for function, arguments in tasks]
        return [future.result() for future in futures]


def all_ready(probes: list[Probe]) -> bool:
    return bool(probes) and all(probe.ok for probe in probes)


class RunRecorder:
    def __init__(self, command: str) -> None:
        started = datetime.now().astimezone()
        self.run_id = f"{started:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
        self.command = command
        self.started_at = started.isoformat(timespec="seconds")
        self.events: list[dict[str, Any]] = []
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        self.log_path = LOG_ROOT / f"{self.run_id}.jsonl"

    def record(self, event: str, **payload: Any) -> None:
        row = {"timestamp": now_iso(), "run_id": self.run_id, "event": event, **payload}
        self.events.append(row)
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    def finish(self, passed: bool, summary: dict[str, Any]) -> dict[str, Any]:
        result = {
            "run_id": self.run_id,
            "command": self.command,
            "started_at": self.started_at,
            "finished_at": now_iso(),
            "passed": passed,
            "external_ai_api_used": False,
            "log_path": str(self.log_path.relative_to(ROOT)),
            "summary": summary,
        }
        self.record("run_finished", passed=passed, summary=summary)
        _write_latest_reports(result)
        return result


def _write_latest_reports(result: dict[str, Any]) -> None:
    json_path = REPORT_ROOT / "operational_stability_latest.json"
    md_path = REPORT_ROOT / "operational_stability_latest.md"
    temp_json = json_path.with_suffix(".json.tmp")
    temp_md = md_path.with_suffix(".md.tmp")
    temp_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = result.get("summary", {})
    lines = [
        "# 운영 안정성 최신 검증 결과",
        "",
        f"- 실행 ID: `{result['run_id']}`",
        f"- 실행 항목: `{result['command']}`",
        f"- 시작: {result['started_at']}",
        f"- 종료: {result['finished_at']}",
        f"- 최종 판정: **{'통과' if result['passed'] else '확인 필요'}**",
        "- 외부 AI API 사용: 아니요",
        f"- 누적 로그: `{result['log_path']}`",
        "",
        "## 결과 요약",
        "",
    ]
    for key, value in summary.items():
        rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
        lines.append(f"- {key}: {rendered}")
    temp_md.write_text("\n".join(map(str, lines)) + "\n", encoding="utf-8")
    temp_json.replace(json_path)
    temp_md.replace(md_path)


def wait_until_ready(timeout_seconds: int = 180, interval_seconds: float = 3.0) -> tuple[bool, list[Probe]]:
    deadline = time.monotonic() + timeout_seconds
    latest: list[Probe] = []
    while time.monotonic() < deadline:
        latest = probe_all()
        if all_ready(latest):
            return True, latest
        time.sleep(interval_seconds)
    return False, latest


def run_baseline(recorder: RunRecorder) -> dict[str, Any]:
    probes = probe_all()
    container_stats = _docker_stats()
    recorder.record("baseline", probes=[asdict(probe) for probe in probes], container_stats=container_stats)
    return {
        "passed": all_ready(probes),
        "service_count": len(probes),
        "ready_count": sum(probe.ok for probe in probes),
        "probes": [asdict(probe) for probe in probes],
        "container_stats": container_stats,
    }


def _mock_request(index: int, timeout_seconds: float = 8.0) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = httpx.post(
            CHAT_MOCK_URL,
            json={"question": f"운영 안정성 모의 요청 {index}", "is_latency_test": True},
            timeout=timeout_seconds,
        )
        elapsed = (time.perf_counter() - started) * 1000
        return {"ok": response.status_code == 200, "status": response.status_code, "latency_ms": round(elapsed, 2)}
    except httpx.HTTPError as error:
        elapsed = (time.perf_counter() - started) * 1000
        return {"ok": False, "status": None, "latency_ms": round(elapsed, 2), "error": f"{type(error).__name__}: {error}"}


def run_concurrency(recorder: RunRecorder, users: tuple[int, ...] = (1, 10, 25)) -> dict[str, Any]:
    phases: list[dict[str, Any]] = []
    for user_count in users:
        started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=user_count) as executor:
            rows = list(executor.map(_mock_request, range(1, user_count + 1)))
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        latencies = [float(row["latency_ms"]) for row in rows]
        phase = {
            "users": user_count,
            "requests": len(rows),
            "successes": sum(bool(row["ok"]) for row in rows),
            "failures": sum(not bool(row["ok"]) for row in rows),
            "p50_ms": percentile(latencies, 0.50),
            "p95_ms": percentile(latencies, 0.95),
            "max_ms": round(max(latencies, default=0.0), 2),
            "phase_duration_ms": duration_ms,
        }
        phases.append(phase)
        recorder.record("concurrency_phase", **phase)
    passed = all(phase["failures"] == 0 for phase in phases)
    return {"passed": passed, "phases": phases}


def run_soak(
    recorder: RunRecorder,
    duration_seconds: int,
    interval_seconds: float,
    request: Callable[[int], dict[str, Any]] = _mock_request,
) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + duration_seconds
    samples = 0
    failures = 0
    request_latencies: list[float] = []
    while time.monotonic() < deadline:
        samples += 1
        probes = probe_all()
        mock = request(samples)
        ok = all_ready(probes) and bool(mock.get("ok"))
        failures += 0 if ok else 1
        request_latencies.append(float(mock.get("latency_ms", 0.0)))
        recorder.record(
            "soak_sample",
            sample=samples,
            ok=ok,
            ready_count=sum(probe.ok for probe in probes),
            service_count=len(probes),
            mock=mock,
        )
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(interval_seconds, remaining))
    elapsed = round(time.monotonic() - started, 2)
    return {
        "passed": failures == 0 and samples > 0,
        "duration_seconds": elapsed,
        "samples": samples,
        "failures": failures,
        "mock_p95_ms": percentile(request_latencies, 0.95),
    }


def _run_docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _docker_stats() -> list[dict[str, Any]]:
    completed = _run_docker("stats", "--no-stream", "--format", "{{json .}}", check=False)
    if completed.returncode:
        return [{"error": completed.stderr.strip() or "Docker 자원 사용량을 읽지 못했습니다."}]
    rows: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = str(payload.get("Name") or "")
        if name.startswith("total-"):
            rows.append({
                "name": name,
                "cpu": payload.get("CPUPerc"),
                "memory": payload.get("MemUsage"),
                "memory_percent": payload.get("MemPerc"),
                "network_io": payload.get("NetIO"),
                "block_io": payload.get("BlockIO"),
            })
    return sorted(rows, key=lambda row: str(row.get("name")))


def _prometheus_sample_count() -> int:
    try:
        response = httpx.get(
            "http://127.0.0.1:9090/api/v1/query",
            params={"query": "count({__name__=~\"ai_.*|voc_.*|k6_.*\"})"},
            timeout=5.0,
        )
        result = response.json().get("data", {}).get("result", [])
        return int(float(result[0]["value"][1])) if result else 0
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return 0


def run_docker_restart(recorder: RunRecorder) -> dict[str, Any]:
    before_count = _prometheus_sample_count()
    before = _run_docker("compose", "ps", "-q").stdout.splitlines()
    recorder.record("docker_restart_started", container_count=len(before), prometheus_series=before_count)
    completed = _run_docker("compose", "restart", check=False)
    ready, probes = wait_until_ready()
    after_count = _prometheus_sample_count()
    passed = completed.returncode == 0 and ready and len(before) >= 10 and after_count > 0
    result = {
        "passed": passed,
        "restart_exit_code": completed.returncode,
        "container_count": len(before),
        "ready_count": sum(probe.ok for probe in probes),
        "service_count": len(probes),
        "prometheus_series_before": before_count,
        "prometheus_series_after": after_count,
        "stderr": completed.stderr.strip(),
    }
    recorder.record("docker_restart_finished", **result)
    return result


def _voc_agents_ready() -> tuple[bool, dict[str, Any]]:
    try:
        response = httpx.get(VOC_AGENTS_HEALTH_URL, timeout=5.0)
        payload = response.json()
        return response.status_code == 200 and bool(payload) and all(row.get("ready") for row in payload.values()), payload
    except (httpx.HTTPError, json.JSONDecodeError, AttributeError):
        return False, {}


def _prometheus_target_ready(job: str) -> tuple[bool, str]:
    try:
        response = httpx.get("http://127.0.0.1:9090/api/v1/targets", timeout=5.0)
        targets = response.json().get("data", {}).get("activeTargets", [])
    except (httpx.HTTPError, json.JSONDecodeError, AttributeError):
        return False, "Prometheus 수집 대상 조회 실패"
    target = next((row for row in targets if row.get("labels", {}).get("job") == job), None)
    if not target:
        return False, f"{job} 수집 대상 없음"
    health = str(target.get("health") or "unknown")
    detail = str(target.get("lastError") or health)
    return health == "up", detail


def run_network_variation(recorder: RunRecorder) -> dict[str, Any]:
    container = _run_docker("compose", "ps", "-q", "voc-api").stdout.strip()
    if not container:
        result = {"passed": False, "error": "실행 중인 VOC API 컨테이너를 찾지 못했습니다."}
        recorder.record("network_variation_finished", **result)
        return result
    inspect = _run_docker(
        "inspect",
        container,
        "--format",
        "{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}",
    )
    networks = [line.strip() for line in inspect.stdout.splitlines() if line.strip()]
    network = next((name for name in networks if name.endswith("_default")), networks[0] if networks else "")
    if not network:
        result = {"passed": False, "error": "VOC API 컨테이너의 Compose 네트워크를 찾지 못했습니다."}
        recorder.record("network_variation_finished", **result)
        return result

    disconnected = False
    degraded_observed = False
    reconnect_error = ""
    recorder.record("network_variation_started", container=container, network=network)
    try:
        _run_docker("network", "disconnect", network, container)
        disconnected = True
        time.sleep(2.0)
        ready_during, agents_during = _voc_agents_ready()
        degraded_observed = not ready_during
        recorder.record("network_disconnected", degraded_observed=degraded_observed, agents=agents_during)
    finally:
        if disconnected:
            # 일반 network connect만 사용하면 Compose 서비스 별칭 `voc-api`가
            # 사라져 Prometheus가 컨테이너를 찾지 못한다. 서비스 별칭도 복원한다.
            reconnect = _run_docker(
                "network", "connect", "--alias", "voc-api", network, container, check=False
            )
            reconnect_error = reconnect.stderr.strip()

    recovered = False
    prometheus_recovered = False
    prometheus_detail = "확인 전"
    agents_after: dict[str, Any] = {}
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        recovered, agents_after = _voc_agents_ready()
        prometheus_recovered, prometheus_detail = _prometheus_target_ready("voc")
        if recovered and prometheus_recovered:
            break
        time.sleep(2.0)
    result = {
        "passed": degraded_observed and recovered and prometheus_recovered,
        "network": network,
        "degraded_observed": degraded_observed,
        "recovered": recovered,
        "prometheus_voc_target_recovered": prometheus_recovered,
        "prometheus_voc_target_detail": prometheus_detail,
        "reconnect_error": reconnect_error,
        "agents_after": agents_after,
    }
    recorder.record("network_variation_finished", **result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AllStar 비과금 운영 안정성 검증")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("baseline", help="핵심 HTTP/TCP 서비스 상태 기록")
    subparsers.add_parser("concurrency", help="모의 채팅 1명·10명·25명 동시 요청")
    soak = subparsers.add_parser("soak", help="장시간 상태·모의 채팅 반복 점검")
    soak.add_argument("--duration-seconds", type=int, default=1800)
    soak.add_argument("--interval-seconds", type=float, default=10.0)
    subparsers.add_parser("docker-restart", help="_Total Compose 재시작 및 자동 복구 확인")
    subparsers.add_parser("network-variation", help="VOC API의 Compose 네트워크 분리·자동 재연결")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    recorder = RunRecorder(args.command)
    try:
        if args.command == "baseline":
            summary = run_baseline(recorder)
        elif args.command == "concurrency":
            summary = run_concurrency(recorder)
        elif args.command == "soak":
            if args.duration_seconds < 1 or args.interval_seconds <= 0:
                raise ValueError("실행 시간과 확인 간격은 0보다 커야 합니다.")
            summary = run_soak(recorder, args.duration_seconds, args.interval_seconds)
        elif args.command == "docker-restart":
            summary = run_docker_restart(recorder)
        elif args.command == "network-variation":
            summary = run_network_variation(recorder)
        else:
            raise ValueError(f"지원하지 않는 실행 항목입니다: {args.command}")
        result = recorder.finish(bool(summary.get("passed")), summary)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["passed"] else 1
    except Exception as error:  # 자동화 결과에 예상하지 못한 예외도 남긴다.
        recorder.record("run_error", error=f"{type(error).__name__}: {error}")
        result = recorder.finish(False, {"error": f"{type(error).__name__}: {error}"})
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
