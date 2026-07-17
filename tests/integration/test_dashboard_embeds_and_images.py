import json
from pathlib import Path

from allstar.ui.dashboard import views


def test_grafana_height_uses_last_panel_and_iframe_disables_scrolling(tmp_path, monkeypatch):
    dashboard = tmp_path / "dashboard.json"
    dashboard.write_text(
        json.dumps({"panels": [{"gridPos": {"y": 20, "h": 20}}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(views, "GRAFANA_DASHBOARD_PATHS", {"test-dashboard": dashboard})

    assert views._grafana_embed_height("test-dashboard") == 1690
    source = Path(views.__file__).read_text(encoding="utf-8")
    assert "components.iframe(url, height=_grafana_embed_height(uid), scrolling=False)" in source


def test_report_markdown_renders_relative_image_in_original_position(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    assets.mkdir()
    image_path = assets / "chart.png"
    image_path.write_bytes(b"png")
    report = tmp_path / "report.md"
    report.write_text("# 앞부분\n\n![한글 그래프](assets/chart.png)\n\n## 뒷부분\n", encoding="utf-8")
    markdown_calls = []
    image_calls = []
    warning_calls = []
    monkeypatch.setattr(views.st, "markdown", lambda value, **kwargs: markdown_calls.append(value))
    monkeypatch.setattr(views.st, "image", lambda value, **kwargs: image_calls.append((value, kwargs)))
    monkeypatch.setattr(views.st, "warning", lambda value, **kwargs: warning_calls.append(value))

    used = views._render_report_markdown_with_images(report)

    assert used == {image_path.resolve()}
    assert image_calls == [(str(image_path.resolve()), {"caption": "한글 그래프", "width": "stretch"})]
    assert "# 앞부분" in markdown_calls[0]
    assert "## 뒷부분" in markdown_calls[-1]
    assert not warning_calls


def test_report_image_path_rejects_parent_escape(tmp_path):
    report = tmp_path / "reports" / "report.md"
    report.parent.mkdir()

    assert views._resolve_report_image(report, "../outside.png") is None


def test_docker_report_images_install_and_select_korean_font():
    root = Path(__file__).resolve().parents[2]
    ai_chart = (root / "src/allstar/ai_agent/evaluation/live_report_charts.py").read_text(encoding="utf-8")
    voc_chart = (root / "src/allstar/voc/evaluation/report_charts.py").read_text(encoding="utf-8")
    ai_docker = (root / "ops/docker/Dockerfile.ai_agent").read_text(encoding="utf-8")
    voc_docker = (root / "ops/docker/Dockerfile.voc").read_text(encoding="utf-8")

    assert "NotoSansCJK-Regular.ttc" in ai_chart and "NotoSansCJK-Bold.ttc" in ai_chart
    assert "NotoSansCJK-Regular.ttc" in voc_chart and "NotoSansCJK-Bold.ttc" in voc_chart
    assert "fonts-noto-cjk" in ai_docker
    assert "fonts-noto-cjk" in voc_docker
