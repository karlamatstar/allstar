from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "scripts" / "run_operational_stability.py"
SPEC = importlib.util.spec_from_file_location("run_operational_stability", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_percentile_uses_nearest_rank() -> None:
    assert MODULE.percentile([1, 2, 3, 4], 0.50) == 2
    assert MODULE.percentile([1, 2, 3, 4], 0.95) == 4
    assert MODULE.percentile([], 0.95) == 0


def test_all_ready_requires_every_service() -> None:
    ready = MODULE.Probe("ready", True, 1.0, "ok")
    failed = MODULE.Probe("failed", False, 2.0, "error")
    assert MODULE.all_ready([ready]) is True
    assert MODULE.all_ready([ready, failed]) is False
    assert MODULE.all_ready([]) is False


def test_concurrency_summary_keeps_independent_1_10_25_phases(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(MODULE, "LOG_ROOT", tmp_path / "logs")
    monkeypatch.setattr(MODULE, "REPORT_ROOT", tmp_path / "reports")
    monkeypatch.setattr(
        MODULE,
        "_mock_request",
        lambda index: {"ok": True, "status": 200, "latency_ms": 10.0 + index},
    )
    recorder = MODULE.RunRecorder("concurrency")

    summary = MODULE.run_concurrency(recorder)

    assert summary["passed"] is True
    assert [phase["users"] for phase in summary["phases"]] == [1, 10, 25]
    assert [phase["requests"] for phase in summary["phases"]] == [1, 10, 25]
    assert all(phase["failures"] == 0 for phase in summary["phases"])


def test_soak_marks_failed_sample_without_external_api(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(MODULE, "LOG_ROOT", tmp_path / "logs")
    monkeypatch.setattr(MODULE, "REPORT_ROOT", tmp_path / "reports")
    monkeypatch.setattr(
        MODULE,
        "probe_all",
        lambda: [MODULE.Probe("api", True, 1.0, "ok")],
    )
    recorder = MODULE.RunRecorder("soak")

    summary = MODULE.run_soak(
        recorder,
        duration_seconds=1,
        interval_seconds=0.01,
        request=lambda index: {"ok": index != 1, "latency_ms": 5.0},
    )

    assert summary["samples"] > 1
    assert summary["failures"] == 1
    assert summary["passed"] is False


def test_network_reconnect_restores_compose_service_alias() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"network", "connect", "--alias", "voc-api"' in source
    assert '_prometheus_target_ready("voc")' in source
    assert '"prometheus_voc_target_recovered": prometheus_recovered' in source
