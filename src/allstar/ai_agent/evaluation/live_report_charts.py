"""AI Agent 실시간 대화 보고서에 삽입할 데이터 기반 PNG 그래프를 생성한다."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1200
HEIGHT = 680
BACKGROUND = "#F7F9FC"
INK = "#1F2937"
MUTED = "#657084"
GRID = "#D8DEE9"
MODEL_COLORS = ("#7C5CC4", "#3568B8")
DECISION_ORDER = ("PASS", "REVIEW", "FAIL", "N/A", "미채점")
AXIS_ORDER = (
    ("accuracy_score", "정확성"),
    ("groundedness_score", "근거성"),
    ("helpfulness_score", "유용성"),
    ("safety_score", "안전성"),
    ("understandability_score", "이해가능성"),
)


def _font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + ".tmp" + path.suffix)
    image.save(temporary, format="PNG")
    temporary.replace(path)


def _canvas(title: str, subtitle: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((55, 34), title, fill=INK, font=_font(31, bold=True))
    if subtitle:
        draw.text((55, 79), subtitle, fill=MUTED, font=_font(18))
    return image, draw


def _empty_chart(path: Path, title: str, message: str) -> None:
    image, draw = _canvas(title)
    draw.rounded_rectangle((160, 220, WIDTH - 160, 465), radius=24, fill="#FFFFFF", outline=GRID, width=2)
    box = draw.textbbox((0, 0), message, font=_font(26, bold=True))
    draw.text(((WIDTH - (box[2] - box[0])) / 2, 320), message, fill="#7B8495", font=_font(26, bold=True))
    _save(image, path)


def _grouped_bar_chart(
    path: Path,
    title: str,
    labels: list[str],
    series: list[tuple[str, list[float | None]]],
    *,
    maximum: float | None = None,
    subtitle: str = "",
) -> None:
    numeric = [value for _name, values in series for value in values if value is not None]
    if not numeric:
        _empty_chart(path, title, "표시할 데이터가 없습니다")
        return

    upper = maximum or max(1.0, max(numeric) * 1.18)
    image, draw = _canvas(title, subtitle)
    left, top, right, bottom = 110, 165, WIDTH - 55, HEIGHT - 115
    for tick in range(6):
        value = upper * tick / 5
        y = bottom - (bottom - top) * tick / 5
        draw.line((left, y, right, y), fill=GRID, width=1)
        draw.text((45, y - 10), f"{value:.0f}", fill=MUTED, font=_font(15))
    draw.line((left, top, left, bottom), fill=INK, width=2)
    draw.line((left, bottom, right, bottom), fill=INK, width=2)

    slot = (right - left) / max(1, len(labels))
    group_width = min(slot * 0.72, 230)
    bar_width = group_width / max(1, len(series))
    for label_index, label in enumerate(labels):
        center = left + slot * (label_index + 0.5)
        start = center - group_width / 2
        for series_index, (_name, values) in enumerate(series):
            value = values[label_index]
            if value is None or value == 0:
                continue
            height = (bottom - top) * min(value, upper) / upper
            x1 = start + series_index * bar_width + 3
            x2 = start + (series_index + 1) * bar_width - 3
            draw.rounded_rectangle(
                (x1, bottom - height, x2, bottom),
                radius=5,
                fill=MODEL_COLORS[series_index % len(MODEL_COLORS)],
            )
            value_text = f"{value:.1f}" if value % 1 else f"{value:.0f}"
            value_box = draw.textbbox((0, 0), value_text, font=_font(15, bold=True))
            draw.text(
                ((x1 + x2 - (value_box[2] - value_box[0])) / 2, bottom - height - 24),
                value_text,
                fill=INK,
                font=_font(15, bold=True),
            )
        label_font = _font(14, bold=True)
        label_box = draw.textbbox((0, 0), label, font=label_font)
        draw.text((center - (label_box[2] - label_box[0]) / 2, bottom + 18), label, fill=INK, font=label_font)

    legend_x = 65
    for index, (name, _values) in enumerate(series):
        draw.rectangle((legend_x, 117, legend_x + 22, 139), fill=MODEL_COLORS[index % len(MODEL_COLORS)])
        draw.text((legend_x + 30, 114), name, fill=INK, font=_font(16))
        legend_x += int(30 + draw.textlength(name, font=_font(16)) + 45)
    _save(image, path)


def _line_chart(path: Path, title: str, labels: list[str], values: list[float]) -> None:
    if not values:
        _empty_chart(path, title, "측정된 응답시간이 없습니다")
        return

    upper = max(1.0, max(values) * 1.15)
    image, draw = _canvas(title, "최근 대화 최대 30건 · 단위 ms")
    left, top, right, bottom = 110, 155, WIDTH - 55, HEIGHT - 115
    for tick in range(6):
        value = upper * tick / 5
        y = bottom - (bottom - top) * tick / 5
        draw.line((left, y, right, y), fill=GRID, width=1)
        draw.text((38, y - 10), f"{value:.0f}", fill=MUTED, font=_font(15))
    draw.line((left, top, left, bottom), fill=INK, width=2)
    draw.line((left, bottom, right, bottom), fill=INK, width=2)

    if len(values) == 1:
        xs = [(left + right) / 2]
    else:
        xs = [left + (right - left) * index / (len(values) - 1) for index in range(len(values))]
    points = [(x, bottom - (bottom - top) * value / upper) for x, value in zip(xs, values)]
    if len(points) > 1:
        draw.line(points, fill="#3568B8", width=4)
    for index, (x, y) in enumerate(points):
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill="#3568B8", outline="#FFFFFF", width=2)
        if len(points) <= 12 or index in (0, len(points) - 1):
            draw.text((x - 17, y - 28), f"{values[index]:.0f}", fill=INK, font=_font(14, bold=True))
    label_step = max(1, len(labels) // 10)
    for index, (x, label) in enumerate(zip(xs, labels)):
        if index % label_step == 0 or index == len(labels) - 1:
            draw.text((x - 14, bottom + 18), label, fill=INK, font=_font(14))
    _save(image, path)


def generate_live_report_charts(df, assets_dir: Path) -> dict[str, Path]:
    """누적 실시간 로그 DataFrame에서 판정·항목 점수·응답시간 그래프를 만든다."""
    assets_dir.mkdir(parents=True, exist_ok=True)

    decision_path = assets_dir / "decision_distribution.png"
    decision_series = []
    for model, label in (("rule", "규칙 기반"), ("api", "서버 연결 방식(API)")):
        model_rows = df[df["model"] == model]
        decision_series.append(
            (label, [float((model_rows["overall_decision"] == decision).sum()) for decision in DECISION_ORDER])
        )
    decision_max = max(value for _label, values in decision_series for value in values)
    _grouped_bar_chart(
        decision_path,
        "모델별 채점 판정 분포",
        list(DECISION_ORDER),
        decision_series,
        maximum=max(5.0, decision_max * 1.15),
        subtitle="N/A와 미채점은 FAIL과 별도로 표시합니다",
    )

    axis_path = assets_dir / "quality_axis_average.png"
    scored = df[df["overall_decision"].isin(["PASS", "REVIEW", "FAIL"])]
    axis_series = []
    for model, label in (("rule", "규칙 기반"), ("api", "서버 연결 방식(API)")):
        model_rows = scored[scored["model"] == model]
        values = []
        for column, _axis_label in AXIS_ORDER:
            numeric = model_rows[column].dropna()
            values.append(float(numeric.mean()) if not numeric.empty else None)
        axis_series.append((label, values))
    _grouped_bar_chart(
        axis_path,
        "모델별 품질 항목 평균 점수",
        [label for _column, label in AXIS_ORDER],
        axis_series,
        maximum=5,
        subtitle="채점 가능한 PASS·REVIEW·FAIL 결과만 집계 · 항목별 5점 만점",
    )

    latency_path = assets_dir / "response_latency_trend.png"
    key_columns = ["request_id"] if df["request_id"].notna().any() else ["timestamp", "question"]
    conversations = (
        df.sort_values("timestamp")
        .drop_duplicates(subset=key_columns, keep="last")
        .tail(30)
    )
    latency_values = [float(value) for value in conversations["latency_ms"].dropna().tolist()]
    labels = [f"{index + 1}" for index in range(len(latency_values))]
    _line_chart(latency_path, "대화별 응답시간 추이", labels, latency_values)

    return {
        "decisions": decision_path,
        "axes": axis_path,
        "latency": latency_path,
    }
