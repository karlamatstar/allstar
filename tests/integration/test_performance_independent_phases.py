"""서버 연결 성능 시험의 단계별 독립 실행과 보고서 집계를 검증한다."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "tools" / "scripts" / "run_performance_tests.py"
SPEC = importlib.util.spec_from_file_location("run_performance_tests", SCRIPT_PATH)
assert SPEC and SPEC.loader
performance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(performance)


def test_k6_phases_run_sequentially_with_stabilization_wait(tmp_path, monkeypatch):
    calls = []
    waits = []

    class FakeProcess:
        def __init__(self, command, env, **_kwargs):
            calls.append((command, env.copy()))
            output_path = Path(command[2].removeprefix("--out=json="))
            point = {
                "type": "Point",
                "metric": "http_req_duration",
                "data": {
                    "value": int(env["PHASE_VUS"]) * 100,
                    "tags": {"tc_id": "TC-001", "phase_id": env["PHASE_ID"]},
                },
            }
            output_path.write_text(json.dumps(point) + "\n", encoding="utf-8")
            self.stdout = []

        @staticmethod
        def wait():
            return 0

    monkeypatch.setattr(performance.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(performance.time, "sleep", waits.append)

    raw_path = performance.run_k6_performance(
        "k6", ROOT / "ops" / "performance" / "api_latency_test.js",
        "127.0.0.1:8000", tmp_path,
    )

    assert [(env["PHASE_ID"], env["PHASE_VUS"]) for _cmd, env in calls] == [
        ("phase1", "1"),
        ("phase2", "10"),
        ("phase3", "25"),
    ]
    assert waits == [5, 5]
    assert len(raw_path.read_text(encoding="utf-8").splitlines()) == 3


def test_report_uses_explicit_phase_tags_instead_of_time_windows(tmp_path):
    raw_path = tmp_path / "raw_latency.json"
    points = []
    for phase_id, values in {
        "phase1": [100],
        "phase2": [200, 300],
        "phase3": [400, 500, 600],
    }.items():
        for value in values:
            points.append({
                "type": "Point",
                "metric": "http_req_duration",
                "data": {
                    "value": value,
                    "tags": {"tc_id": "TC-001", "phase_id": phase_id},
                },
            })
    raw_path.write_text(
        "".join(json.dumps(point) + "\n" for point in points),
        encoding="utf-8",
    )

    report_path = performance.parse_and_generate_report(raw_path, tmp_path / "reports")
    report = report_path.read_text(encoding="utf-8")

    assert "단계별 독립 실행" in report
    assert "**1단계 (1명 동시접속)**: 100.0 ms / 완료 요청 1건" in report
    assert "**2단계 (10명 동시접속)**: 250.0 ms / 완료 요청 2건" in report
    assert "**3단계 (25명 동시접속)**: 500.0 ms / 완료 요청 3건" in report


def test_k6_script_has_no_fixed_20_second_phase_schedule():
    source = (ROOT / "ops" / "performance" / "api_latency_test.js").read_text(encoding="utf-8")

    assert "PHASE_ID" in source
    assert "PHASE_VUS" in source
    assert "startTime: '20s'" not in source
    assert "startTime: '40s'" not in source
