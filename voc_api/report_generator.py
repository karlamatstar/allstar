"""실시간 VOC 대화 로그만 사용해 Markdown 리포트와 manifest를 생성한다."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from config.model_profiles import public_profiles


ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs" / "voc" / "live" / "conversations"
REPORT_DIR = ROOT / "quality" / "reports" / "voc" / "live"
MANIFEST_DIR = ROOT / "logs" / "report_manifests"


def _records() -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    sources: list[str] = []
    for path in sorted(LOG_DIR.glob("*.jsonl")):
        sources.append(str(path.relative_to(ROOT)))
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows, sources


def generate_live_report() -> dict:
    rows, sources = _records()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    history = REPORT_DIR / "history"
    latest = REPORT_DIR / "latest"
    history.mkdir(exist_ok=True)
    latest.mkdir(exist_ok=True)

    lines = [
        "# VOC 실시간 대화 품질 리포트",
        "",
        f"> 생성 시각: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"> 포함 질문: {len(rows)}건",
        "",
        "## A~D 모델 프로필",
        "",
        "A~D는 질문 1건에 적용되는 답변 생성 모델과 독립 품질 평가 모델의 조합이다.",
        "",
        "| 프로필 | 의미 | 생성 모델 | 평가 모델 |",
        "|---|---|---|---|",
    ]
    for profile in public_profiles():
        generation = profile["generation"]
        judge = profile["judge"]
        lines.append(
            f"| {profile['profile_id']} | {profile['summary']} | "
            f"{generation['provider']} / {generation['model']} / {generation['reasoning']} | "
            f"{judge['provider']} / {judge['model']} / {judge['reasoning']} |"
        )

    lines.extend(["", "## 질문별 결과 요약", ""])
    if not rows:
        lines.append("아직 저장된 실시간 질문이 없다.")
    for index, row in enumerate(rows, 1):
        profile = row.get("profile", {})
        generation = profile.get("generation", {})
        judge = profile.get("judge", {})
        result = row.get("result") or {}
        score = row.get("judge") or {}
        lines.extend([
            f"### {index}. {row.get('question', '')}",
            "",
            f"- 요청 ID: `{row.get('request_id', '')}`",
            f"- 사용 프로필: **{row.get('profile_id', '')}** · {profile.get('title', '')}",
            f"- 생성: `{generation.get('provider', '')} / {generation.get('model', '')} / {generation.get('reasoning', '')}`",
            f"- 평가: `{judge.get('provider', '')} / {judge.get('model', '')} / {judge.get('reasoning', '')}`",
            f"- 상태: `{row.get('status', '')}`",
            f"- 처리시간: `{row.get('elapsed_seconds', 0)}초`",
            f"- Judge: `{score.get('total', 'N/A')} / {score.get('verdict', 'N/A')}`",
            "",
            result.get("answer") or result.get("policy") or result.get("summary") or "결과 없음",
            "",
        ])

    content = "\n".join(lines).rstrip() + "\n"
    history_path = history / f"voc_live_report_{run_id}.md"
    latest_path = latest / "voc_live_report.md"
    history_path.write_text(content, encoding="utf-8")
    latest_path.write_text(content, encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "report_type": "voc_live",
        "run_id": run_id,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "record_count": len(rows),
        "profiles": sorted({row.get("profile_id") for row in rows if row.get("profile_id")}),
        "sources": sources,
        "outputs": [str(history_path.relative_to(ROOT)), str(latest_path.relative_to(ROOT))],
    }
    manifest_path = MANIFEST_DIR / f"voc_live_{run_id}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"report": str(latest_path), "history": str(history_path), "manifest": str(manifest_path)}
