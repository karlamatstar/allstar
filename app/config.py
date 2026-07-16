import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# 챗봇 대화/채점 로그는 quality/reports/live_log/에 남긴다 (배치 리포트의 quality/reports/testcase_log/와 대응)
LOG_DIR = BASE_DIR / "quality" / "reports" / "live_log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

JIRA_URL = os.getenv("JIRA_URL")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "BUG")
JIRA_EPIC_KEY = os.getenv("JIRA_EPIC_KEY", "BUG-1")
JIRA_SPRINT_ID = os.getenv("JIRA_SPRINT_ID", "36")

def validate_config() -> None:
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY가 없습니다. "
            f"{BASE_DIR / '.env'} 파일에 OPENAI_API_KEY=발급받은키 형식으로 입력하세요."
        )
