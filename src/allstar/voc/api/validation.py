from __future__ import annotations


def is_valid_question_text(value: object) -> bool:
    """문자 인코딩 손상으로 물음표만 남은 요청을 외부 API 호출 전에 차단한다."""
    text = str(value or "").strip()
    compact = "".join(character for character in text if not character.isspace())
    meaningful = [character for character in compact if character.isalnum()]
    question_marks = sum(character in {"?", "？"} for character in compact)
    if len(meaningful) < 2:
        return False
    if question_marks >= max(3, len(compact) // 2):
        return False
    return True
