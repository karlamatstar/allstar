import json
from pathlib import Path

from allstar.ui.dashboard import views


def test_ai_case_change_archive_preserves_current_list(tmp_path, monkeypatch):
    cases_path = tmp_path / "test_cases.json"
    monkeypatch.setattr(views, "AI_CASES_PATH", cases_path)
    cases = [{"case_id": "TC-001", "category": "정확성", "test_type": "Happy"}]

    archive_path = views._archive_ai_case_document(cases)

    assert archive_path.parent == tmp_path / "archive" / "revisions"
    assert archive_path.name.startswith("test_cases_before_change_")
    assert json.loads(archive_path.read_text(encoding="utf-8")) == cases


def test_ai_case_edit_ui_preserves_id_and_locks_changes_during_run():
    source = Path(views.__file__).read_text(encoding="utf-8")

    assert "기존 AI 에이전트 테스트케이스 확인·수정" in source
    assert 'text_input("테스트케이스 ID", value=selected_id, disabled=True)' in source
    assert "_archive_ai_case_document(cases)" in source
    assert 'submitted = st.form_submit_button("테스트케이스 저장", type="primary", disabled=running)' in source
    assert 'disabled=running or not (delete_ids and confirm)' in source
