"""VOC A~D 정식 보고서를 Prometheus 수치 지표로 변환한다."""

from __future__ import annotations

import json
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from prometheus_client.core import GaugeMetricFamily

from allstar.shared.paths import PACKAGE_ROOT, VOC_REPORT_ROOT


RESULTS = ("PASS", "REVIEW", "FAIL", "N/A")
DEFAULT_REPORT_ROOT = VOC_REPORT_ROOT / "testcase"
DEFAULT_RUBRIC_PATH = PACKAGE_ROOT / "voc" / "evaluation" / "judge_rubric.json"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def classify_case_result(row: dict[str, Any]) -> str:
    """정식 보고서 판정을 Grafana용 네 가지 상태로 단순화한다."""
    verdict = str(row.get("verdict") or "")
    if verdict.startswith("PASS"):
        return "PASS"
    total = _number(row.get("total"))
    if total is None:
        return "N/A"
    if total >= 90:
        return "PASS"
    if total >= 80:
        return "REVIEW"
    return "FAIL"


def _timestamp(value: Any) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


class VocTestcaseReportCollector:
    """공유 `_OUTPUT`의 최신 A~D 보고서를 매 수집 시점에 안전하게 읽는다."""

    def __init__(
        self,
        report_root: Path = DEFAULT_REPORT_ROOT,
        rubric_path: Path = DEFAULT_RUBRIC_PATH,
    ) -> None:
        self.report_root = Path(report_root)
        self.rubric_path = Path(rubric_path)
        self._lock = threading.RLock()
        self._cache: dict[Path, tuple[int, int, dict[str, Any]]] = {}

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        key = (stat.st_mtime_ns, stat.st_size)
        with self._lock:
            cached = self._cache.get(path)
            if cached and cached[:2] == key:
                return cached[2]
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                return None
            if not isinstance(data, dict):
                return None
            self._cache[path] = (*key, data)
            return data

    def _criteria(self) -> list[tuple[str, float]]:
        rubric = self._read_json(self.rubric_path) or {}
        criteria: list[tuple[str, float]] = []
        for item in rubric.get("criteria") or []:
            name = str(item.get("name") or "").strip()
            maximum = _number(item.get("max_score"))
            if name and maximum and maximum > 0:
                criteria.append((name, maximum))
        return criteria

    def _reports(self):
        for profile in "ABCD":
            path = self.report_root / profile.lower() / "llm_judge_result.json"
            report = self._read_json(path)
            if not report:
                continue
            cases = report.get("cases")
            if not isinstance(cases, list) or not cases:
                continue
            yield profile, report, [row for row in cases if isinstance(row, dict)]

    def collect(self):
        average_score = GaugeMetricFamily(
            "voc_testcase_latest_average_score",
            "최신 VOC 테스트케이스 정상 평가 평균 점수",
            labels=["profile"],
        )
        cases_total = GaugeMetricFamily(
            "voc_testcase_latest_cases_total",
            "최신 VOC 테스트케이스 보고서 전체 사례 수",
            labels=["profile"],
        )
        result_counts = GaugeMetricFamily(
            "voc_testcase_latest_case_results",
            "최신 VOC 테스트케이스 PASS REVIEW FAIL N/A 사례 수",
            labels=["profile", "result"],
        )
        total_duration = GaugeMetricFamily(
            "voc_testcase_latest_duration_seconds",
            "최신 VOC 테스트케이스 전체 처리시간 합계",
            labels=["profile"],
        )
        average_duration = GaugeMetricFamily(
            "voc_testcase_latest_case_average_duration_seconds",
            "최신 VOC 테스트케이스 평균 처리시간",
            labels=["profile"],
        )
        case_score = GaugeMetricFamily(
            "voc_testcase_latest_case_score",
            "최신 VOC 테스트케이스별 품질 점수",
            labels=["profile", "case_id", "result"],
        )
        case_duration = GaugeMetricFamily(
            "voc_testcase_latest_case_duration_seconds",
            "최신 VOC 테스트케이스별 처리시간",
            labels=["profile", "case_id"],
        )
        criterion_percent = GaugeMetricFamily(
            "voc_testcase_latest_criterion_achievement_percent",
            "최신 VOC 테스트케이스 평가 항목별 평균 달성률",
            labels=["profile", "criterion"],
        )
        report_timestamp = GaugeMetricFamily(
            "voc_testcase_last_report_timestamp_seconds",
            "최신 VOC 테스트케이스 보고서 갱신 Unix 시간",
            labels=["profile"],
        )

        criteria = self._criteria()
        for profile, report, cases in self._reports():
            scores = [value for row in cases if (value := _number(row.get("total"))) is not None]
            durations = [value for row in cases if (value := _number(row.get("total_seconds"))) is not None]
            counts = Counter(classify_case_result(row) for row in cases)

            cases_total.add_metric([profile], len(cases))
            if scores:
                average_score.add_metric([profile], sum(scores) / len(scores))
            for result in RESULTS:
                result_counts.add_metric([profile, result], counts[result])
            if durations:
                total_duration.add_metric([profile], sum(durations))
                average_duration.add_metric([profile], sum(durations) / len(durations))

            for row in cases:
                case_id = str(row.get("case_id") or "-")
                result = classify_case_result(row)
                score = _number(row.get("total"))
                duration = _number(row.get("total_seconds"))
                if score is not None:
                    case_score.add_metric([profile, case_id, result], score)
                if duration is not None:
                    case_duration.add_metric([profile, case_id], duration)

            for criterion, maximum in criteria:
                values = [value for row in cases if (value := _number(row.get(criterion))) is not None]
                if values:
                    achievement = (sum(values) / len(values)) / maximum * 100
                    criterion_percent.add_metric([profile, criterion], achievement)

            generated_at = _timestamp(report.get("generated_at"))
            if generated_at is not None:
                report_timestamp.add_metric([profile], generated_at)

        yield average_score
        yield cases_total
        yield result_counts
        yield total_duration
        yield average_duration
        yield case_score
        yield case_duration
        yield criterion_percent
        yield report_timestamp
