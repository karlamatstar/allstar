# AllStar AI Agent + VOC 통합 프로젝트

기존 AI Agent 품질 포트폴리오와 VOC 멀티 에이전트를 하나의 실행·로그·리포트 체계로 통합한 프로젝트다.

## 서비스 구성

- AI Agent FastAPI: `http://localhost:8000`
- VOC FastAPI Gateway: `http://localhost:8100`
- Streamlit 통합 화면: `http://localhost:8501`
- VOC gRPC 에이전트: `6001~6006`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Streamlit은 Windows 호스트에서 실행하고, 나머지 서버는 Docker Compose로 실행한다. Server Control Center에서 함께 시작·종료하고 서비스별 로그를 확인할 수 있다.

## 최초 준비

```powershell
cd D:\_Study_Project\_Total
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
Copy-Item .env.example .env
```

`.env`에 필요한 API 키를 입력한다. `.env`는 Git에 포함되지 않는다.

## 실행

1. Docker Desktop을 실행한다.
2. `RUN\start_servers.bat`를 더블클릭한다.
3. Server Control Center에서 `전체 시작`을 누른다.
4. Streamlit 행의 `접속` 버튼을 누른다.

CMD 창의 순간적인 표시도 피하려면 `RUN\start_servers_hidden.vbs`를 실행한다. QA 도구는 `RUN\start_qa.bat` 또는 `RUN\start_qa_hidden.vbs`로 연다.

## 디렉터리 구조

- 제품 코드: `src/allstar/`
- Server·QA GUI와 실행 보조 도구: `tools/`
- Docker·모니터링·성능 시험 설정: `ops/`
- 자동 테스트: `tests/`
- 더블클릭 실행 파일: `RUN/`
- 원본 로그: `_OUTPUT/logs/`
- 사람이 확인하는 리포트: `_OUTPUT/reports/`
- 설계·운영 문서: `_DOCS/`

모든 Python 패키지는 `allstar.*` 이름을 사용한다. 공통 경로는 `src/allstar/shared/paths.py`, A~D 모델 정의는 `src/allstar/shared/model_profiles.py`에서 관리한다.

## VOC A~D 프로필

| 프로필 | 생성 | 독립 Judge |
|---|---|---|
| A | OpenAI `gpt-5.6-luna` · none | Anthropic `claude-sonnet-5` · low |
| B | Anthropic `claude-sonnet-4-6` · low | OpenAI `gpt-5.6-terra` · low |
| C | OpenAI `gpt-5.6-luna` · none | OpenAI `gpt-5.6-terra` · low |
| D | Anthropic `claude-sonnet-4-6` · low | Anthropic `claude-sonnet-5` · low |

챗봇에서 A~D를 선택하며, 질문별 선택 프로필·생성 모델·Judge 모델·추론 설정은 로그와 리포트에 함께 기록한다.

## 비AI 검증

```powershell
.\.venv\Scripts\python.exe -m compileall -q src tools tests
.\.venv\Scripts\python.exe -m pytest -q `
  --ignore=tests/ai_agent/test_negative_cases.py `
  --ignore=tests/ai_agent/test_evaluation_pipeline.py `
  --ignore=tests/voc/evaluation/test_pipeline_e2e.py `
  -k "not end_to_end"
docker compose config --quiet
```

실제 AI API 테스트는 대표 케이스 `TC-01`, `TC-02`만 사용한다. QA GUI에서 실험군과 예상 호출 범위를 확인한 뒤 별도로 실행한다.

상세 구조와 구현 상태는 `_DOCS/README.md`에서 안내한다.
