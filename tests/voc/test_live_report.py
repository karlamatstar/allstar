import json
from pathlib import Path

from allstar.shared.model_profiles import get_profile
from allstar.voc.api import report_generator


def test_live_report_starts_with_profile_guide_and_records_question_profile(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    report_dir = tmp_path / "reports"
    manifest_dir = tmp_path / "manifests"
    log_dir.mkdir()
    profile = get_profile("C")
    row = {
        "request_id": "req-1",
        "timestamp": "2026-07-16T01:00:00+00:00",
        "question": "배송 불만 분석",
        "profile_id": "C",
        "profile": profile.snapshot(),
        "status": "completed",
        "elapsed_seconds": 3.2,
        "result": {"answer": "배송 불만 요약과 개선안"},
        "judge": {
            "rubric_version": "voc_9x100_v1",
            "total": 88,
            "verdict": "조건부 배포 가능, 개선 후 재검증",
            "scores": {"Interpreter 해석 정확성": 13},
            "reasons": {"Interpreter 해석 정확성": "질문 의도를 적절히 파악함"},
            "rationale": "전반적으로 양호함",
        },
    }
    deployable = {
        **row,
        "request_id": "req-2",
        "timestamp": "2026-07-16T02:00:00+00:00",
        "question": "정상 배포 결과",
        "profile_id": "A",
        "profile": get_profile("A").snapshot(),
        "judge": {
            **row["judge"],
            "total": 95,
            "verdict": "배포 가능",
        },
    }
    (log_dir / "2026-07-16.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in (row, deployable)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(report_generator, "LOG_DIR", log_dir)
    monkeypatch.setattr(report_generator, "REPORT_DIR", report_dir)
    monkeypatch.setattr(report_generator, "MANIFEST_DIR", manifest_dir)
    monkeypatch.setattr(report_generator, "ROOT", tmp_path)

    output = report_generator.generate_live_report()
    content = (report_dir / "latest" / "voc_live_report.md").read_text(encoding="utf-8")
    history = Path(output["history"]).read_text(encoding="utf-8")
    manifest = json.loads(Path(output["manifest"]).read_text(encoding="utf-8"))
    assert "## 1. 모델 프로필과 품질평가 기준" in content
    assert "### A~D 모델 프로필" in content
    assert "### 독립 품질평가 기준" in content
    assert "## 2. 한눈에 보는 품질 현황" in content
    assert "## 3. 품질·판정·처리시간 그래프" in content
    assert "## 4. 확인이 필요한 채점 결과" in content
    assert "## 5. 채팅 및 채점 목록" in content
    assert content.index("## 1. 모델 프로필과 품질평가 기준") < content.index("## 2. 한눈에 보는 품질 현황")
    assert "A~D 모델과 9항목·100점 기준 열기" not in content
    assert "9항목·100점" in content
    assert "프로필: **C · OpenAI 계열 비교**" in content
    assert "gpt-5.6-luna" in content
    assert "13/15" in content
    assert "정상 100점 채점: **2건**" in content
    assert "90점 미만·N/A·실패 상세 목록 열기 (1건)" in content
    assert content.count("정상 배포 결과") == 1
    assert "assets/profile_decision_distribution.png" in content
    assert "/profile_decision_distribution.png" in history
    assert manifest["attention_count"] == 1
    assets = report_dir / "latest" / "assets"
    assert {path.name for path in assets.glob("*.png")} == {
        "profile_decision_distribution.png",
        "profile_quality_axis_average.png",
        "profile_average_duration.png",
    }
    assert all(path.read_bytes().startswith(b"\x89PNG") for path in assets.glob("*.png"))
    assert output["manifest"].endswith(".json")


def test_live_report_preserves_but_excludes_damaged_question(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    report_dir = tmp_path / "reports"
    manifest_dir = tmp_path / "manifests"
    log_dir.mkdir()
    rows = [
        {"request_id": "valid", "question": "보험 가입 문제점", "profile_id": "A", "judge": {"rubric_version": "voc_9x100_v1"}},
        {"request_id": "broken", "question": "?? ?? ???", "profile_id": "A", "judge": {"rubric_version": "voc_9x100_v1"}},
    ]
    (log_dir / "2026-07-17.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(report_generator, "LOG_DIR", log_dir)
    monkeypatch.setattr(report_generator, "REPORT_DIR", report_dir)
    monkeypatch.setattr(report_generator, "MANIFEST_DIR", manifest_dir)
    monkeypatch.setattr(report_generator, "ROOT", tmp_path)

    output = report_generator.generate_live_report()
    content = (report_dir / "latest" / "voc_live_report.md").read_text(encoding="utf-8")
    manifest = json.loads(Path(output["manifest"]).read_text(encoding="utf-8"))

    assert "정상 100점 채점: **1건**" in content
    assert "입력 손상 제외: 1건" in content
    assert "## 6. 무효 입력 기록" in content
    assert "<details>" in content
    assert manifest["valid_count"] == 1
    assert manifest["invalid_count"] == 1
