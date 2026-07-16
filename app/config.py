import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
AI_AGENT_LIVE_LOG_ROOT = BASE_DIR / "logs" / "ai_agent" / "live"
CONVERSATION_LOG_DIR = AI_AGENT_LIVE_LOG_ROOT / "conversations"
JUDGMENT_LOG_DIR = AI_AGENT_LIVE_LOG_ROOT / "judgments"
CONVERSATION_LOG_DIR.mkdir(parents=True, exist_ok=True)
JUDGMENT_LOG_DIR.mkdir(parents=True, exist_ok=True)

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
