# AllStar AI Agent + VOC 통합 프로젝트

기존 `ai_agent_quality_portfolio`와 `voc_upgrade`의 기능을 `_Total` 안에서 통합한 로컬·수업용 프로젝트다.

## 현재 구성

- Portfolio FastAPI: `http://localhost:8000`
- VOC FastAPI Gateway: `http://localhost:8100`
- Streamlit 통합 대시보드: `http://localhost:8501`
- VOC gRPC 에이전트: `6001~6006`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Streamlit은 Windows 호스트에서 실행하고 나머지 서버는 Docker Compose로 실행한다.

## 최초 준비

```powershell
cd D:\_Study_Project\_Total
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에 실제 API 키를 입력한다. `.env`는 Git에 올라가지 않는다.

## 실행

1. Docker Desktop을 실행한다.
2. `RUN\start_server_control.bat`를 더블클릭한다.
3. `전체 시작`을 누른다.
4. Streamlit 행의 `접속` 버튼을 누른다.

CMD 창의 순간 표시까지 숨기려면 `RUN\start_server_control_hidden.vbs`를 실행한다.

QA는 `RUN\start_qa_control.bat`에서 실행한다.

## 저장 구조

- AI Agent 품질 코드: `ai_quality/`
- AI Agent·VOC 리포트: `quality/reports/ai_agent/`, `quality/reports/voc/`
- 대화·채점·테스트 원본 로그: `logs/ai_agent/`, `logs/voc/`
- 서버와 GUI 실행 로그: `logs/services/`
- 리포트 근거 목록: `logs/report_manifests/`

원본 로그를 `quality/reports/`에 저장하지 않는다. `quality/reports/`에는 사람이 확인하는 결과 리포트만 둔다.

## VOC A~D

A~D는 질문 한 건에 적용되는 생성 모델과 독립 Judge 모델의 조합이다.

| 프로필 | 생성 | 독립 Judge |
|---|---|---|
| A | OpenAI `gpt-5.6-luna` · none | Anthropic `claude-sonnet-5` · low |
| B | Anthropic `claude-sonnet-4-6` · low | OpenAI `gpt-5.6-terra` · low |
| C | OpenAI `gpt-5.6-luna` · none | OpenAI `gpt-5.6-terra` · low |
| D | Anthropic `claude-sonnet-4-6` · low | Anthropic `claude-sonnet-5` · low |

모델 정의의 단일 원본은 `config/model_profiles.py`다. 챗봇과 QA GUI가 같은 정의를 사용한다.

## 비AI 검증

```powershell
.\.venv\Scripts\python.exe -m pytest tests --ignore=tests/test_negative_cases.py --ignore=tests/test_quality_pipeline.py -q
docker compose config --quiet
```

실제 AI API 테스트는 대표 케이스 2개만 사용하며 QA GUI에서 실험군과 예상 호출 범위를 확인한 뒤 실행한다.

상세 구현 상태는 `_DOCS/INTEGRATED_PROJECT_IMPLEMENTATION.md`를 참고한다.
