import json
from pathlib import Path

from allstar.ui.dashboard import views


def test_voc_case_change_archive_preserves_document(tmp_path, monkeypatch):
    monkeypatch.setattr(views, "VOC_CASES_PATH", tmp_path / "test_cases.json")
    document = {
        "description": "현재 실행본",
        "cases": [{"case_id": "TC-01", "question": "기존 질문"}],
    }

    archive_path = views._archive_voc_case_document(document)

    assert archive_path.parent == tmp_path / "archive" / "revisions"
    assert json.loads(archive_path.read_text(encoding="utf-8")) == document


def test_voc_case_edit_ui_keeps_original_archive_read_only():
    source = Path(views.__file__).read_text(encoding="utf-8")

    assert "기존 VOC 테스트케이스 확인·수정" in source
    assert "선택한 테스트케이스 수정 저장" in source
    assert "archive_source_case_id" in source
    assert "archive/revisions" not in source  # 경로는 안전한 Path 조합으로만 구성한다.
    assert '_archive_voc_case_document(document)' in source
    assert 'disabled=running' in source
