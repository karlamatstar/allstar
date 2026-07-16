def validate_by_rules(
    user_question: str,
    ai_answer: str,
    expected_keyword: str,
) -> dict:
    keywords = [k.strip().lower() for k in expected_keyword.split('|')]
    keyword_found = any(k in ai_answer.lower() for k in keywords)

    return {
        "keyword_found": keyword_found,
        "rule_status": "PASS" if keyword_found else "FAIL",
        "rule_reason": (
            f"예상 핵심 키워드('{expected_keyword}') 중 하나가 답변에 포함되어 있습니다."
            if keyword_found else
            f"예상 핵심 키워드('{expected_keyword}')가 답변에 포함되지 않았습니다."
        ),
    }
