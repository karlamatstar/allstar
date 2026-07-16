"""QA 실행 로그를 누적하고 최신 요약 보고서를 갱신한다."""

from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from allstar.shared.paths import LOG_ROOT, MANIFEST_ROOT, PROJECT_ROOT, REPORT_ROOT


QA_LOG_ROOT = LOG_ROOT / "qa"
QA_REPORT_ROOT = REPORT_ROOT / "qa" / "latest"
QA_MANIFEST_ROOT = MANIFEST_ROOT / "qa"
QA_EVENT_LOG = QA_LOG_ROOT / "qa_runs.jsonl"
_EVENT_LOCK = threading.Lock()


def _now() -> datetime:
    return datetime.now().astimezone()


def _safe_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _append_event(event: dict[str, Any]) -> None:
    QA_EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _EVENT_LOCK, QA_EVENT_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")


def _metric_value(summary: dict[str, Any], metric: str, key: str) -> float | int | None:
    values = summary.get("metrics", {}).get(metric, {}).get("values", {})
    value = values.get(key)
    return value if isinstance(value, (int, float)) else None


def parse_k6_summary(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        "request_count": _metric_value(summary, "http_reqs", "count"),
        "failure_rate": _metric_value(summary, "http_req_failed", "rate"),
        "response_time_avg_ms": _metric_value(summary, "http_req_duration", "avg"),
        "response_time_p95_ms": _metric_value(summary, "http_req_duration", "p(95)"),
        "checks_passed": _metric_value(summary, "checks", "passes"),
        "checks_failed": _metric_value(summary, "checks", "fails"),
    }


def parse_pytest_summary(text: str) -> dict[str, int]:
    metrics: dict[str, int] = {}
    names = {
        "passed": "passed",
        "failed": "failed",
        "error": "errors",
        "errors": "errors",
        "skipped": "skipped",
        "deselected": "deselected",
    }
    for count, raw_name in re.findall(
        r"(\d+)\s+(passed|failed|errors?|skipped|deselected)\b", text, re.IGNORECASE
    ):
        name = names[raw_name.lower()]
        metrics[name] = max(metrics.get(name, 0), int(count))
    return metrics


def detect_execution_warnings(text: str) -> list[str]:
    """종료 코드가 0이어도 결과가 불완전한 대표 경고를 찾는다."""
    warnings: list[str] = []
    patterns = (
        ("독립 평가 실패", r"Judge 실패"),
        ("외부 AI API 실패", r"(?:API|Anthropic|OpenAI).{0,80}(?:실패|invalid|401)"),
        ("미평가 결과 발생", r"미평가\(API 실패\)|\bN/A\s+-"),
    )
    for label, pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            warnings.append(label)
    return warnings


def _display(value: Any, suffix: str = "") -> str:
    if value is None:
        return "측정값 없음"
    if isinstance(value, float):
        return f"{value:.3f}{suffix}"
    return f"{value}{suffix}"


@dataclass
class QAReportSession:
    """한 번의 QA 실행에 대한 누적 로그와 최신 보고서를 관리한다."""

    test_id: str
    test_name: str
    command: list[str]
    settings: dict[str, Any] = field(default_factory=dict)
    run_id: str = field(default_factory=lambda: f"{_now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}")
    started_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.log_path = QA_LOG_ROOT / "runs" / self.test_id / f"{self.run_id}.log"
        self.k6_summary_path = (
            QA_LOG_ROOT / "k6" / self.test_id / f"{self.run_id}_summary.json"
            if len(self.command) >= 2 and Path(self.command[0]).name.lower() in {"k6", "k6.exe"}
            else None
        )
        self.report_path = QA_REPORT_ROOT / f"{self.test_id}.md"
        self.latest_report_path = QA_REPORT_ROOT / "latest_report.md"
        self.manifest_path = QA_MANIFEST_ROOT / f"{self.test_id}.json"
        self.latest_manifest_path = QA_MANIFEST_ROOT / "latest.json"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if self.k6_summary_path:
            self.k6_summary_path.parent.mkdir(parents=True, exist_ok=True)

    def command_for_execution(self) -> list[str]:
        if self.k6_summary_path and len(self.command) >= 3 and self.command[1] == "run":
            return [
                self.command[0],
                "run",
                f"--summary-export={self.k6_summary_path}",
                *self.command[2:],
            ]
        return list(self.command)

    def start(self) -> None:
        header = {
            "run_id": self.run_id,
            "test_id": self.test_id,
            "test_name": self.test_name,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "command": self.command_for_execution(),
            "settings": self.settings,
        }
        self.log_path.write_text(
            "[QA 실행 정보]\n" + json.dumps(header, ensure_ascii=False, indent=2) + "\n\n[실행 출력]\n",
            encoding="utf-8",
        )
        _append_event({"event": "started", "status": "running", **header, "log": _safe_relative(self.log_path)})

    def append_output(self, text: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(text)

    def finish(
        self,
        status: str,
        exit_code: int | None,
        error: str | None = None,
        *,
        record_event: bool = True,
        append_footer: bool = True,
        finished_at: datetime | None = None,
    ) -> dict[str, Any]:
        finished_at = finished_at or _now()
        duration_seconds = max(0.0, (finished_at - self.started_at).total_seconds())
        try:
            output = self.log_path.read_text(encoding="utf-8")
        except OSError:
            output = ""
        metrics = parse_k6_summary(self.k6_summary_path)
        pytest_metrics = parse_pytest_summary(output)
        if pytest_metrics:
            metrics["pytest"] = pytest_metrics
        warnings = detect_execution_warnings(output)
        effective_status = "completed_with_warnings" if status == "completed" and warnings else status
        formal_reports: list[str] = []
        if self.test_id.startswith("voc_profile_"):
            profile_id = self.test_id.rsplit("_", 1)[-1]
            formal_path = REPORT_ROOT / "voc" / "testcase" / profile_id / "quality_score_report.md"
            if formal_path.exists():
                formal_reports.append(_safe_relative(formal_path))

        result = {
            "schema_version": 1,
            "report_type": "qa_latest",
            "run_id": self.run_id,
            "test_id": self.test_id,
            "test_name": self.test_name,
            "status": effective_status,
            "process_status": status,
            "exit_code": exit_code,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "duration_seconds": round(duration_seconds, 3),
            "settings": self.settings,
            "metrics": metrics,
            "warnings": warnings,
            "formal_reports": formal_reports,
            "error": error,
            "sources": [_safe_relative(self.log_path)] + (
                [_safe_relative(self.k6_summary_path)] if self.k6_summary_path and self.k6_summary_path.exists() else []
            ),
            "report": _safe_relative(self.report_path),
        }
        report = self._render_report(result)
        _atomic_write(self.report_path, report)
        _atomic_write(self.latest_report_path, report)
        manifest = json.dumps(result, ensure_ascii=False, indent=2)
        _atomic_write(self.manifest_path, manifest)
        _atomic_write(self.latest_manifest_path, manifest)
        if record_event:
            _append_event({"event": "finished", **result})
        if append_footer:
            self.append_output(
                f"\n[실행 종료]\n상태: {effective_status}\n종료 코드: {exit_code}\n"
                f"완료 시각: {result['finished_at']}\n보고서: {result['report']}\n"
            )
        return result

    def _render_report(self, result: dict[str, Any]) -> str:
        status_labels = {
            "completed": "완료",
            "failed": "실패",
            "cancelled": "사용자 중지",
            "start_failed": "시작 실패",
            "completed_with_warnings": "경고 포함 완료",
        }
        lines = [
            f"# {self.test_name} 최신 실행 요약",
            "",
            "> 이 파일은 정식 품질 보고서가 아니라 최근 실행 상태와 증적을 연결하는 보조 요약입니다. 같은 시험을 다시 실행하면 최신 결과로 갱신되며 원문 실행 로그는 누적 보존됩니다.",
            "",
            "## 실행 요약",
            "",
            f"- 실행 식별자: `{result['run_id']}`",
            f"- 상태: **{status_labels.get(result['status'], result['status'])}**",
            f"- 시작 시각: {result['started_at']}",
            f"- 완료 시각: {result['finished_at']}",
            f"- 총 실행시간: {_display(result['duration_seconds'], '초')}",
            f"- 종료 코드: {_display(result['exit_code'])}",
        ]
        if self.settings:
            lines.extend(["", "## 실행 조건", ""])
            lines.extend(f"- {key}: {value}" for key, value in self.settings.items())

        metrics = result["metrics"]
        lines.extend(["", "## 결과 지표", ""])
        if any(key in metrics for key in ("request_count", "failure_rate", "response_time_avg_ms", "response_time_p95_ms")):
            failure_rate = metrics.get("failure_rate")
            failure_percent = failure_rate * 100 if isinstance(failure_rate, (int, float)) else None
            lines.extend([
                f"- 전체 요청 수: {_display(metrics.get('request_count'))}",
                f"- 요청 실패율: {_display(failure_percent, '%')}",
                f"- 평균 응답시간: {_display(metrics.get('response_time_avg_ms'), 'ms')}",
                f"- p95 응답시간: {_display(metrics.get('response_time_p95_ms'), 'ms')}",
                f"- 검사 성공/실패: {_display(metrics.get('checks_passed'))} / {_display(metrics.get('checks_failed'))}",
            ])
        elif "pytest" in metrics:
            pytest = metrics["pytest"]
            lines.extend([
                f"- 통과: {pytest.get('passed', 0)}",
                f"- 실패: {pytest.get('failed', 0)}",
                f"- 오류: {pytest.get('errors', 0)}",
                f"- 제외: {pytest.get('skipped', 0)}",
                f"- 선택 제외: {pytest.get('deselected', 0)}",
            ])
        else:
            lines.append("- 별도 수치 지표가 없는 시험입니다. 성공 여부와 원문 실행 로그를 기준으로 확인합니다.")

        if result["warnings"]:
            lines.extend(["", "## 확인이 필요한 경고", ""])
            lines.extend(f"- {warning}" for warning in result["warnings"])

        if result["formal_reports"]:
            lines.extend(["", "## 정식 결과 보고서", ""])
            lines.extend(f"- `{report}`" for report in result["formal_reports"])

        lines.extend([
            "",
            "## 증적",
            "",
            f"- 누적 원문 로그: `{_safe_relative(self.log_path)}`",
        ])
        if self.k6_summary_path and self.k6_summary_path.exists():
            lines.append(f"- k6 원본 요약: `{_safe_relative(self.k6_summary_path)}`")
        if result.get("error"):
            lines.extend(["", "## 오류", "", str(result["error"])])
        return "\n".join(lines) + "\n"
