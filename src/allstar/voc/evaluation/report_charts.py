"""VOC 정식 보고서에 삽입할 데이터 기반 PNG 그래프를 생성한다."""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1200
HEIGHT = 680
BACKGROUND = "#F7F9FC"
INK = "#1F2937"
GRID = "#D8DEE9"
COLORS = ("#3568B8", "#3B9B77", "#E59A32", "#B05A7A")


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


def _number(value) -> float | None:
    try:
        if value in (None, "", "N/A"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


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
        draw.text((55, 79), subtitle, fill="#657084", font=_font(18))
    return image, draw


def _empty_chart(path: Path, title: str, message: str) -> None:
    image, draw = _canvas(title)
    draw.rounded_rectangle((160, 220, WIDTH - 160, 465), radius=24, fill="#FFFFFF", outline=GRID, width=2)
    box = draw.textbbox((0, 0), message, font=_font(26, bold=True))
    x = (WIDTH - (box[2] - box[0])) / 2
    draw.text((x, 320), message, fill="#7B8495", font=_font(26, bold=True))
    _save(image, path)


def _bar_chart(
    path: Path,
    title: str,
    labels: list[str],
    values: list[float | None],
    *,
    maximum: float | None = None,
    suffix: str = "",
    subtitle: str = "",
) -> None:
    numeric = [value for value in values if value is not None]
    if not numeric:
        _empty_chart(path, title, "평가된 점수가 없습니다")
        return
    upper = maximum or max(numeric) * 1.15 or 1.0
    image, draw = _canvas(title, subtitle)
    left, top, right, bottom = 120, 145, WIDTH - 65, HEIGHT - 105
    draw.line((left, top, left, bottom), fill=INK, width=2)
    draw.line((left, bottom, right, bottom), fill=INK, width=2)
    for tick in range(6):
        value = upper * tick / 5
        y = bottom - (bottom - top) * tick / 5
        draw.line((left, y, right, y), fill=GRID, width=1)
        draw.text((55, y - 10), f"{value:.0f}", fill="#657084", font=_font(15))
    slot = (right - left) / max(1, len(labels))
    bar_width = min(120, slot * 0.56)
    for index, (label, value) in enumerate(zip(labels, values)):
        center = left + slot * (index + 0.5)
        if value is None:
            draw.rounded_rectangle((center - bar_width / 2, bottom - 9, center + bar_width / 2, bottom), radius=3, fill="#B8C0CC")
            value_text = "N/A"
        else:
            height = (bottom - top) * min(value, upper) / upper
            draw.rounded_rectangle((center - bar_width / 2, bottom - height, center + bar_width / 2, bottom), radius=8, fill=COLORS[index % len(COLORS)])
            value_text = f"{value:.1f}{suffix}"
        text_box = draw.textbbox((0, 0), value_text, font=_font(18, bold=True))
        value_x = center - (text_box[2] - text_box[0]) / 2
        value_y = bottom - ((bottom - top) * value / upper if value is not None else 0) - 32
        draw.text((value_x, value_y), value_text, fill=INK, font=_font(18, bold=True))
        label_box = draw.textbbox((0, 0), label, font=_font(18, bold=True))
        draw.text((center - (label_box[2] - label_box[0]) / 2, bottom + 18), label, fill=INK, font=_font(18, bold=True))
    _save(image, path)


def _grouped_bar_chart(
    path: Path,
    title: str,
    labels: list[str],
    series: list[tuple[str, list[float | None]]],
    *,
    suffix: str = "",
    maximum: float | None = None,
    integer_axis: bool = False,
) -> None:
    numeric = [value for _name, values in series for value in values if value is not None]
    if not numeric:
        _empty_chart(path, title, "측정된 데이터가 없습니다")
        return
    upper = maximum or max(numeric) * 1.18 or 1.0
    image, draw = _canvas(title)
    left, top, right, bottom = 110, 165, WIDTH - 55, HEIGHT - 115
    if integer_axis:
        upper = max(1, float(int(max(numeric) + 0.999999)))
        tick_values = [float(value) for value in range(int(upper) + 1)]
    else:
        tick_values = [upper * tick / 5 for tick in range(6)]
    for value in tick_values:
        y = bottom - (bottom - top) * value / upper
        draw.line((left, y, right, y), fill=GRID, width=1)
        draw.text((45, y - 10), f"{value:.0f}", fill="#657084", font=_font(15))
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
            if value is None:
                continue
            height = (bottom - top) * value / upper
            x1 = start + series_index * bar_width + 3
            x2 = start + (series_index + 1) * bar_width - 3
            draw.rectangle((x1, bottom - height, x2, bottom), fill=COLORS[series_index % len(COLORS)])
        box = draw.textbbox((0, 0), label, font=_font(17, bold=True))
        draw.text((center - (box[2] - box[0]) / 2, bottom + 18), label, fill=INK, font=_font(17, bold=True))
    legend_x = 65
    for index, (name, _values) in enumerate(series):
        draw.rectangle((legend_x, 116, legend_x + 22, 138), fill=COLORS[index % len(COLORS)])
        draw.text((legend_x + 30, 113), name, fill=INK, font=_font(16))
        legend_x += 30 + draw.textlength(name, font=_font(16)) + 45
    draw.text((WIDTH - 130, bottom + 55), suffix, fill="#657084", font=_font(15))
    _save(image, path)


def generate_profile_charts(
    rows: list[dict],
    criteria_names: Iterable[str],
    max_by_name: dict[str, int],
    assets_dir: Path,
) -> dict[str, Path]:
    labels = [str(row.get("case_id") or "-") for row in rows]
    score_path = assets_dir / "case_score_comparison.png"
    _bar_chart(score_path, "테스트케이스 품질 점수 (Case Quality Score)", labels, [_number(row.get("total")) for row in rows], maximum=100, suffix="")

    duration_path = assets_dir / "case_duration_comparison.png"
    _grouped_bar_chart(
        duration_path,
        "테스트케이스 처리시간 (Case Processing Time)",
        labels,
        [
            ("파이프라인", [_number(row.get("pipeline_seconds")) for row in rows]),
            ("Judge", [_number(row.get("judge_seconds")) for row in rows]),
            ("전체", [_number(row.get("total_seconds")) for row in rows]),
        ],
        suffix="초",
    )

    criterion_labels: list[str] = []
    criterion_rates: list[float | None] = []
    for index, name in enumerate(criteria_names, start=1):
        maximum = max_by_name.get(name)
        values = [_number(row.get(name)) for row in rows]
        values = [value for value in values if value is not None]
        criterion_labels.append(f"C{index}")
        criterion_rates.append(statistics.mean(values) / maximum * 100 if values and maximum else None)
    criteria_path = assets_dir / "criteria_score_rate.png"
    _bar_chart(
        criteria_path,
        "평가 항목별 달성률 (Criteria Achievement Rate)",
        criterion_labels,
        criterion_rates,
        maximum=100,
        suffix="%",
        subtitle="C1~C9는 보고서 평가 항목 표의 순서를 따릅니다",
    )
    return {"scores": score_path, "durations": duration_path, "criteria": criteria_path}


def generate_cross_validation_charts(experiment_rows: dict[str, list[dict]], assets_dir: Path) -> dict[str, Path]:
    labels = list("ABCD")
    average_scores: list[float | None] = []
    average_times: list[float | None] = []
    for profile_id in labels:
        rows = experiment_rows.get(profile_id, [])
        scores = [_number(row.get("total")) for row in rows]
        scores = [value for value in scores if value is not None]
        times = [_number(row.get("total_seconds")) for row in rows]
        times = [value for value in times if value is not None]
        average_scores.append(statistics.mean(scores) if scores else None)
        average_times.append(statistics.mean(times) if times else None)
    score_path = assets_dir / "profile_average_score.png"
    _bar_chart(score_path, "A~D 평균 품질 점수", labels, average_scores, maximum=100)
    time_path = assets_dir / "profile_average_duration.png"
    _bar_chart(time_path, "A~D 평균 처리시간", labels, average_times, suffix="초")
    return {"scores": score_path, "durations": time_path}
