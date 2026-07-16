"""비교 평가 결과(케이스마다 rule_based/api_based 두 채점)를 CSV/JSON/Markdown 리포트로 저장한다.
ai_quality_final_project의 비교 리포트 형식에 N/A(채점 불가) 분리 집계를 더한 버전."""
import json
import shutil
from pathlib import Path

import pandas as pd

MODEL_TYPES = ["rule_based", "api_based"]
MODEL_LABELS_MD = {"rule_based": "규칙 기반 챗봇", "api_based": "API 기반 챗봇"}


def save_json_report(results: list, file_path: Path) -> None:
    file_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_rule_status(rule_validation: dict) -> str:
    if "rule_status" in rule_validation:
        return str(rule_validation["rule_status"])
    if "keyword_found" in rule_validation:
        return "PASS" if rule_validation["keyword_found"] else "FAIL"
    return "CHECK"


def _results_to_rows(results: list) -> list:
    """비교 결과를 CSV/요약 통계 공용의 평평한(flat) 행으로 변환한다 (케이스 × 모델 2종 = 행 2개)."""
    rows = []
    for result in results:
        for model_type in MODEL_TYPES:
            model_result = result[model_type]
            evaluation = model_result["evaluation"]
            rows.append({
                "case_id":                result["case_id"],
                "category":               result["category"],
                "test_type":              result["test_type"],
                "model_type":             model_type,
                "user_question":          result["user_question"],
                "ai_answer":              model_result["answer"],
                "rule_status":            get_rule_status(model_result["rule_validation"]),
                "accuracy_score":         evaluation["accuracy"]["score"],
                "groundedness_score":     evaluation["groundedness"]["score"],
                "helpfulness_score":      evaluation["helpfulness"]["score"],
                "safety_score":           evaluation["safety"]["score"],
                "understandability_score": evaluation.get("understandability", {}).get("score", 0),
                "total_score":            evaluation.get("total_score", 0),
                "overall_decision":       evaluation["overall_decision"],
                "summary":                evaluation["summary"],
            })
    return rows


def save_csv_report(results: list, file_path: Path) -> None:
    pd.DataFrame(_results_to_rows(results)).to_csv(file_path, index=False, encoding="utf-8-sig")


# PASS=파랑, REVIEW=노랑, FAIL=빨강, N/A=회색 (ai_quality_final_project와 동일 배색)
DECISION_BADGE_STYLES = {
    "PASS":   ("#2563eb", "#ffffff"),
    "REVIEW": ("#eab308", "#3f2d03"),
    "FAIL":   ("#dc2626", "#ffffff"),
    "N/A":    ("#6b7280", "#ffffff"),
}


def decision_badge(decision: str) -> str:
    bg, fg = DECISION_BADGE_STYLES.get(decision, ("#6b7280", "#ffffff"))
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'padding:3px 12px;border-radius:999px;font-weight:700;font-size:0.95em;">'
        f'{decision}</span>'
    )


TEST_TYPE_BADGE_STYLES = {
    "Happy":    ("#d1fae5", "#065f46"),
    "Edge":     ("#fde8cc", "#92400e"),
    "Negative": ("#fbcfe8", "#9d174d"),
}


def test_type_badge(test_type: str) -> str:
    bg, fg = TEST_TYPE_BADGE_STYLES.get(test_type, ("#e5e7eb", "#374151"))
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'padding:3px 12px;border-radius:999px;font-weight:700;font-size:0.95em;">'
        f'{test_type}</span>'
    )


SCORE_COLS_MD = ["accuracy_score", "groundedness_score", "helpfulness_score", "safety_score", "understandability_score"]
AXIS_LABELS_MD = {
    "accuracy_score": "정확성", "groundedness_score": "근거성", "helpfulness_score": "유용성",
    "safety_score": "안전성", "understandability_score": "이해가능성",
}
TEST_TYPE_ORDER = ["Happy", "Edge", "Negative"]


def _decision_stats(g: pd.DataFrame) -> dict:
    """N/A는 FAIL과 동일하게 취급하여 통과율 분모에 포함시키고 FAIL 건수에 합산한다."""
    n = len(g)
    scored = g.copy()
    scored["overall_decision"] = scored["overall_decision"].replace("N/A", "FAIL")
    scored_n = len(scored)
    return {
        "n": n,
        "na": 0,  # FAIL로 합산되므로 따로 표기 안함
        "pass": int((scored["overall_decision"] == "PASS").sum()),
        "review": int((scored["overall_decision"] == "REVIEW").sum()),
        "fail": int((scored["overall_decision"] == "FAIL").sum()),
        "pass_rate": round((scored["overall_decision"] == "PASS").sum() / scored_n * 100, 1) if scored_n else 0.0,
        "avg_total": round(scored["total_score"].mean(), 2) if scored_n else 0.0,
        "axis_avg": {c: round(scored[c].mean(), 2) for c in SCORE_COLS_MD} if scored_n else {c: 0.0 for c in SCORE_COLS_MD},
    }


def wrap_details(body_lines: list) -> list:
    return ["<details>", "", "<summary> </summary>", ""] + body_lines + ["", "</details>", ""]


def save_markdown_report(results: list, file_path: Path) -> None:
    lines = ["# AI 챗봇 품질관리 최종 비교 보고서", ""]

    lines += [
        "## 1. 평가 목적", "",
        "### 규칙 기반 챗봇과 API 기반 챗봇의 품질을 동일한 테스트 케이스로 비교 평가합니다.", "",
    ]

    # ------------------------------------------------------------------
    # 2. 비교 결과 (케이스 × 두 모델 판정 나란히)
    # ------------------------------------------------------------------
    section2 = [
        "| 테스트 ID | 유형 | 규칙 기반 판정 | API 기반 판정 |",
        "|---|---|---|---|",
    ]
    for result in results:
        section2.append(
            f"| **{result['case_id']}** | "
            f"{test_type_badge(result['test_type'])} | "
            f"{decision_badge(result['rule_based']['evaluation']['overall_decision'])} | "
            f"{decision_badge(result['api_based']['evaluation']['overall_decision'])} |"
        )
    lines += ["## 2. 비교 결과", ""]
    lines += wrap_details(section2)

    # ------------------------------------------------------------------
    # 3. 케이스별 상세 비교
    # ------------------------------------------------------------------
    def score_line(ev: dict) -> str:
        return (
            f"정확성 {ev['accuracy']['score']} | 근거성 {ev['groundedness']['score']} | "
            f"유용성 {ev['helpfulness']['score']} | 안전성 {ev['safety']['score']} | "
            f"이해성 {ev.get('understandability', {}).get('score', 0)} | 합계 {ev.get('total_score', 0)}/25"
        )

    section3 = []
    for i, result in enumerate(results, start=1):
        rb_ev = result["rule_based"]["evaluation"]
        ab_ev = result["api_based"]["evaluation"]
        heading = (
            f"{result['case_id']} · {result['test_type']} · {result['category']} · "
            f"규칙기반 {rb_ev['overall_decision']} / API기반 {ab_ev['overall_decision']}"
        )
        section3 += [
            f"### 3.{i} {heading}", "",
            f"- 사용자 질문: {result['user_question']}",
            "",
            "#### 규칙 기반 챗봇",
            f"- 답변: {result['rule_based']['answer']}",
            f"- 규칙 점검: {get_rule_status(result['rule_based']['rule_validation'])}",
            f"- 점수: {score_line(rb_ev)}",
            f"- 종합 판정: {decision_badge(rb_ev['overall_decision'])}",
            f"- 평가 의견: {rb_ev['summary']}",
            "",
            "#### API 기반 챗봇",
            f"- 답변: {result['api_based']['answer']}",
            f"- 규칙 점검: {get_rule_status(result['api_based']['rule_validation'])}",
            f"- 점수: {score_line(ab_ev)}",
            f"- 종합 판정: {decision_badge(ab_ev['overall_decision'])}",
            f"- 평가 의견: {ab_ev['summary']}",
            "",
        ]
    lines += ["## 3. 케이스별 상세 비교", ""]
    lines += wrap_details(section3)

    # ------------------------------------------------------------------
    # 4. 종합 요약 — 모델별/유형별 집계 (N/A는 통과율 분모에서 제외)
    # ------------------------------------------------------------------
    df = pd.DataFrame(_results_to_rows(results))
    total_cases = df["case_id"].nunique()
    overall = _decision_stats(df)
    model_stats = {m: _decision_stats(g) for m, g in df.groupby("model_type")}
    test_type_stats = {t: _decision_stats(g) for t, g in df.groupby("test_type")}
    ordered_test_types = [t for t in TEST_TYPE_ORDER if t in test_type_stats] + \
        [t for t in test_type_stats if t not in TEST_TYPE_ORDER]

    section4 = [f"- 전체 테스트 케이스: **{total_cases}건** (모델 2종 × 케이스 → 평가 행 {overall['n']}건)"]
    overall_line = (
        f"- 전체 판정 분포: {decision_badge('PASS')} {overall['pass']}건 · "
        f"{decision_badge('REVIEW')} {overall['review']}건 · "
        f"{decision_badge('FAIL')} {overall['fail']}건"
    )
    if overall["na"]:
        overall_line += f" · {decision_badge('N/A')} {overall['na']}건(채점 불가)"
    overall_line += f" (통과율 {overall['pass_rate']}%, N/A 제외)"
    section4 += [overall_line, f"- 전체 평균 종합점수: **{overall['avg_total']} / 25** (N/A 제외)", ""]

    section4 += ["| 모델 | 평가 행 | PASS | REVIEW | FAIL | 통과율 | 평균 종합점수 |", "|---|---|---|---|---|---|---|"]
    for model_type in MODEL_TYPES:
        s = model_stats.get(model_type)
        if not s:
            continue
        section4.append(
            f"| {MODEL_LABELS_MD[model_type]} | {s['n']} | {s['pass']} | {s['review']} | {s['fail']} | "
            f"{s['pass_rate']}% | {s['avg_total']} / 25 |"
        )
    section4.append("")

    if "rule_based" in model_stats and "api_based" in model_stats:
        rb_rate = model_stats["rule_based"]["pass_rate"]
        ab_rate = model_stats["api_based"]["pass_rate"]
        if ab_rate > rb_rate:
            section4.append(
                f"- API 기반 챗봇이 규칙 기반 챗봇보다 통과율이 **{round(ab_rate - rb_rate, 1)}%p 높아** "
                "전반적으로 더 우수한 응답 품질을 보였습니다."
            )
        elif rb_rate > ab_rate:
            section4.append(
                f"- 규칙 기반 챗봇이 API 기반 챗봇보다 통과율이 **{round(rb_rate - ab_rate, 1)}%p 높아** "
                "전반적으로 더 우수한 응답 품질을 보였습니다."
            )
        else:
            section4.append("- 두 모델의 통과율이 동일하여 우열을 가리기 어렵습니다.")
    section4.append("")

    axis_header = " | ".join(AXIS_LABELS_MD[c] for c in SCORE_COLS_MD)
    section4 += [f"| 모델 | {axis_header} |", "|---|" + "---|" * len(SCORE_COLS_MD)]
    for model_type in MODEL_TYPES:
        s = model_stats.get(model_type)
        if not s:
            continue
        scores = " | ".join(str(s["axis_avg"][c]) for c in SCORE_COLS_MD)
        section4.append(f"| {MODEL_LABELS_MD[model_type]} | {scores} |")
    section4.append("")

    section4 += ["**테스트 유형별 판정 분포** (모델 2종 합산)", "", "| 테스트 유형 | 평가 행 | PASS | REVIEW | FAIL | 통과율 |", "|---|---|---|---|---|---|"]
    for t in ordered_test_types:
        s = test_type_stats[t]
        section4.append(f"| {test_type_badge(t)} | {s['n']} | {s['pass']} | {s['review']} | {s['fail']} | {s['pass_rate']}% |")

    lines += ["## 4. 종합 요약", ""]
    lines += wrap_details(section4)

    file_path.write_text("\n".join(lines), encoding="utf-8")


def generate_all(results: list, reports_dir: Path, timestamp: str) -> None:
    """타임스탬프가 붙은 이력본은 reports_dir/history/에, 날짜 없는 최신본은 reports_dir 바로 아래에 저장한다."""
    history_dir = reports_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    ts_json = history_dir / f"{timestamp}_evaluation_result.json"
    ts_csv  = history_dir / f"{timestamp}_evaluation_result.csv"
    ts_md   = history_dir / f"{timestamp}_final_quality_report.md"

    save_json_report(results, ts_json)
    save_csv_report(results, ts_csv)
    save_markdown_report(results, ts_md)

    latest_json = reports_dir / "evaluation_result.json"
    latest_csv  = reports_dir / "evaluation_result.csv"
    latest_md   = reports_dir / "final_quality_report.md"
    shutil.copy2(ts_json, latest_json)
    shutil.copy2(ts_csv, latest_csv)
    shutil.copy2(ts_md, latest_md)

    print(f"  JSON     → {ts_json} (최신본 → {latest_json})")
    print(f"  CSV      → {ts_csv} (최신본 → {latest_csv})")
    print(f"  Markdown → {ts_md} (최신본 → {latest_md})")


if __name__ == "__main__":
    from datetime import datetime
    from allstar.shared.paths import AI_AGENT_REPORT_ROOT

    reports_dir = AI_AGENT_REPORT_ROOT / "batch"
    existing_json = reports_dir / "evaluation_result.json"
    if not existing_json.exists():
        raise SystemExit(
            f"{existing_json} 파일이 없습니다. 먼저 `python -m ai_quality.quality_pipeline`을 한 번 실행해 "
            "평가 결과를 생성한 뒤 다시 시도하세요."
        )

    existing_results = json.loads(existing_json.read_text(encoding="utf-8"))
    timestamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    generate_all(existing_results, reports_dir, timestamp)
    print("\n기존 평가 결과(JSON)를 바탕으로 리포트를 재생성했습니다. (OpenAI API 재호출 없음)")
