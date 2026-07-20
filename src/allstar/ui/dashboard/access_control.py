from __future__ import annotations

import hmac
import os


TEST_TAB_PASSWORD_ENV = "DASHBOARD_TEST_TABS_PASSWORD"
DEFAULT_TEST_TAB_PASSWORD = "1234"


def configured_test_tab_password() -> str:
    """테스트 상위 탭의 현재 비밀번호를 반환한다."""
    return os.getenv(TEST_TAB_PASSWORD_ENV, "").strip() or DEFAULT_TEST_TAB_PASSWORD


def matches_test_tab_password(candidate: str) -> bool:
    """입력값을 현재 설정과 비교하되 비밀번호를 로그에 남기지 않는다."""
    return hmac.compare_digest(str(candidate or ""), configured_test_tab_password())
