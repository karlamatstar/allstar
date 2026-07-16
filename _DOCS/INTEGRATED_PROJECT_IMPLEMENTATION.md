# AllStar 통합 프로젝트 구현 기준서

> 최초 구현일: 2026-07-16
> 대상: `D:\_Study_Project\_Total`
> 기준 준비 문서: `VOC_PORTFOLIO_INTEGRATION_PREPARATION.md`

## 1. 현재 구현 상태

### 디렉터리 개편 적용 상태

- 목표 디렉터리와 명명 규칙은 `PROJECT_DIRECTORY_STRUCTURE.md`에 확정하고 실제 코드에 적용했다.
- 개편 전 기록 기준은 Git 커밋 `80022b0`이다.
- 제품 코드는 `src/allstar/`, 실행 도구는 `tools/`, 운영 설정은 `ops/`, 산출물은 `_OUTPUT/`을 사용한다.
- Python import와 서버 진입점은 `allstar.*` 패키지 기준으로 통일했다.
- 구조 개편 과정에서 A~D 모델 구성, 로그 필드, 보고서 내용은 유지했다.

### 구현 완료

- 기존 AI Agent의 `app`, `ai_quality`, `monitoring`, `performance`, `scripts`, `tests` 자산 통합
- 기존 VOC의 6개 에이전트, gRPC, LLM 래퍼, 유틸리티, QA 소스 복사
- A~D 중앙 모델 프로필 `src/allstar/shared/model_profiles.py`
- 요청별 생성 모델 프로필을 전달하는 gRPC `ModelExecutionConfig`
- Interpreter·Retriever·Summarizer·Evaluator·Critic·Improver의 중복 단계 호출 제거
- Summarizer 중심 단일 오케스트레이션
- VOC FastAPI Gateway `:8100`
- 비동기 `/chat` 요청과 `/chat/{request_id}/status` 조회
- `/profiles`, `/health`, `/agents/health`, `/metrics`
- 대화·Judge JSONL 로그 분리 저장
- A~D 설명과 질문별 프로필을 포함하는 VOC 실시간 Markdown 리포트
- Streamlit 통합 화면의 AI Agent·VOC·리포트·모니터링 영역
- VOC 챗봇 A~D 카드와 실제 모델·추론 설정 표시
- Docker Compose의 Portfolio API, VOC API, VOC 에이전트 6개, Prometheus, Grafana
- Windows 호스트 Streamlit을 함께 제어하는 Server Control Center
- AI Agent QA 8개 구분과 VOC QA를 제공하는 QA Control Center
- `.bat` 및 숨김 실행용 `.vbs` 런처

### 부분 구현

- 7단계 트래커는 처리 중·완료·실패 상태와 전체 경과 시간을 표시한다.
- 각 gRPC 단계의 실시간 진행 이벤트를 별도 스트림으로 전송하는 기능은 아직 없다.
- 완료 뒤 `trace`에는 단계 시간이 남지만 Streamlit 상세 패널은 후속 개선 대상이다.
- 기존 Portfolio 대시보드 원본은 `src/allstar/ui/dashboard/portfolio_legacy.py`에 보존했으며 통합 화면은 핵심 챗봇·링크 중심으로 먼저 구현했다.

### 아직 실행 검증하지 않음

- 실제 OpenAI·Anthropic API 테스트는 사용자 승인 전이라 실행하지 않았다.
- Grafana VOC 전용 완성 대시보드 JSON은 후속 작업이다.
- A~D 교차검증 종합 리포트의 신규 통합 화면은 후속 작업이다.

## 2. 모델 프로필과 실행 원칙

| 프로필 | 답변 생성 | 독립 Judge | 목적 |
|---|---|---|---|
| A | OpenAI `gpt-5.6-luna`, none | Anthropic `claude-sonnet-5`, low | 기본 권장 교차 평가 |
| B | Anthropic `claude-sonnet-4-6`, low | OpenAI `gpt-5.6-terra`, low | 역방향 교차 평가 |
| C | OpenAI `gpt-5.6-luna`, none | OpenAI `gpt-5.6-terra`, low | OpenAI 계열 역할 분리 |
| D | Anthropic `claude-sonnet-4-6`, low | Anthropic `claude-sonnet-5`, low | Anthropic 계열 역할 분리 |

- 서버가 실패한 모델을 다른 제공자로 몰래 대체하지 않는다.
- Judge 실패 시 생성 답변은 유지하고 점수는 N/A로 남긴다.
- 챗봇 질문은 단발이며 이전 대화를 다음 모델 입력에 전달하지 않는다.
- 프로필 전체 스냅샷을 질문 로그와 Judge 로그에 저장한다.

## 3. 실행 구조

```text
Windows 호스트
  ├─ Server Control Center
  └─ Streamlit :8501
        ├─ Portfolio API :8000
        └─ VOC API :8100
              ├─ Interpreter :6001
              ├─ Retriever :6002
              ├─ Summarizer :6003
              ├─ Evaluator :6004
              ├─ Critic :6005
              └─ Improver :6006

Docker Compose
  ├─ Portfolio API
  ├─ VOC API + 에이전트 6개
  ├─ Prometheus :9090
  └─ Grafana :3000
```

## 4. 로그와 리포트

```text
_OUTPUT/logs/ai_agent/live/conversations/conversations.jsonl
_OUTPUT/logs/ai_agent/live/judgments/live_evaluations.jsonl
_OUTPUT/logs/ai_agent/testcase/
_OUTPUT/logs/voc/live/conversations/YYYY-MM-DD.jsonl
_OUTPUT/logs/voc/live/judgments/YYYY-MM-DD.jsonl
_OUTPUT/logs/voc/testcase/a~d/
_OUTPUT/logs/voc/cross_validation/
_OUTPUT/logs/services/
_OUTPUT/reports/manifests/
_OUTPUT/reports/ai_agent/batch/
_OUTPUT/reports/ai_agent/batch/history/
_OUTPUT/reports/ai_agent/live/
_OUTPUT/reports/ai_agent/live/history/
_OUTPUT/reports/voc/live/latest/voc_live_report.md
_OUTPUT/reports/voc/live/history/
_OUTPUT/reports/voc/testcase/a~d/
_OUTPUT/reports/voc/cross_validation/
_OUTPUT/reports/defects/chatbot/
_OUTPUT/reports/defects/chaos/
_OUTPUT/reports/performance/
```

원본 로그와 생성 리포트는 서로 다른 최상위 폴더에 저장한다. 실시간 리포트는 해당 서비스의 실시간 대화·채점 로그만 사용하며 테스트케이스 및 교차검증 결과와 섞지 않는다. 2026-07-16에 기존 `quality/reports/live_log/`, `quality/reports/testcase_log/` 사용을 종료하고 위 구조로 코드·화면·테스트 경로를 이전했다.

실행 코드가 리포트 폴더에 섞이지 않도록 챗봇 결함 기록기는 `src/allstar/ai_agent/evaluation/defect_logger.py`에 두고, Markdown 결과만 `_OUTPUT/reports/defects/chatbot/`에 저장한다. 성능 리포트 화면도 `_OUTPUT/reports/performance/`를 사용한다.

## 5. 2026-07-16 검증 결과

### 통과

- 전체 Python 문법 검사
- gRPC Python 코드 재생성
- Docker Compose 구문 검사 및 서비스 목록 인식
- Docker Desktop 엔진 `29.6.1` 시작 및 전체 이미지 빌드 성공
- Docker 서비스 10개 기동 유지 확인
- Portfolio API `/health` 응답 `200`
- VOC API `/health` 응답 `200`, 에이전트 6개 `ready=true`
- Prometheus Health `200`, `ai-agent`와 `voc` 수집 대상 모두 `up`
- Grafana Health `200`, 데이터베이스 상태 `ok`
- API 키가 없는 VOC 질문은 `503`으로 차단되어 외부 AI 호출 없음
- Streamlit 호스트 기동과 `/_stcore/health` 응답 `200 ok`
- 신규 A~D·VOC API·리포트·gRPC 테스트 50개 통과
- 실제 AI API 테스트 2개를 제외한 통합 프로젝트 테스트 12개 통과
- 추가 VOC 비AI 회귀 테스트 21개 통과, 서버 미가동 조건 2개 건너뜀
- 전체 테스트 14개 수집 성공
- 디렉터리 기준 적용 후 비AI 통합 테스트 16개 통과
- 디렉터리 기준 적용 후 VOC 비AI 회귀 테스트 72개 통과, 환경 조건 1개 건너뜀
- 구조 개편 전 Portfolio Docker 이미지 재빌드 및 `/health` 200 확인
- Streamlit 내장 화면 실행 테스트 통과
- 실제 API 테스트를 포함한 `tests/` 전체 18개 수집 성공

### `src/allstar` 구조 전환 후 추가 검증

- `src`, `tools`, `tests` 전체 Python 문법 검사 통과
- 비AI 안전 명령 기준 100개 통과, 실제 API E2E 이름 2개 선택 제외
- 서버 미가동 상태에서 E2E까지 수집한 확장 회귀는 97개 통과, 환경 조건 5개 건너뜀
- Docker Compose 구성 검사와 전체 이미지 빌드 통과
- Docker 서비스 10개 기동, API·Prometheus·Grafana Health `200`, VOC 에이전트 6개 `ready=true` 확인
- Windows 호스트 Streamlit `/_stcore/health` 응답 `200 ok` 확인
- 실제 OpenAI·Anthropic 호출은 실행하지 않음

### 디렉터리 정렬 검증 참고

- 실제 AI API를 호출하는 테스트는 실행하지 않았다.
- 기존 `voc/quality_diagnosis/test_mcp_tools.py` 전체 실행 중 3건은 이번 경로 변경과 무관한 기존 조건(`voc/main.py` 부재, 별도 로컬 에이전트의 CSV 경로, API 키 미설정)으로 실패했다.
- 경로 변경 대상 모듈과 비AI 회귀 묶음은 위에 기록한 16개 및 72개 테스트로 별도 통과를 확인했다.

### 실행하지 않은 테스트

- `tests/test_negative_cases.py`: 실제 OpenAI API 호출
- `tests/test_quality_pipeline.py`: 대표 2건 실제 OpenAI API 호출
- QA GUI의 VOC A~D: 각 프로필 대표 `TC-01`, `TC-02` 실제 API 호출

실제 API 검증 전에 프로필, 대표 케이스 2개, 예상 호출 범위를 다시 확인한다.

## 6. 다음 작업 우선순위

1. `PROJECT_DIRECTORY_STRUCTURE.md` 기준으로 디렉터리 구조 개편
2. import, Docker, Streamlit, Server·QA GUI 및 로그·리포트 경로 비AI 회귀 검증
3. API 키 설정 후 A 프로필 대표 2건 실제 검증
4. 단계별 실시간 이벤트와 상세 결과 패널 구현
5. VOC Grafana 대시보드 추가
6. A~D 교차검증 종합 리포트 화면 완성
7. 실제 GUI 사용 후 Server Control 로그 화면 개선점 반영

AWS 또는 외부 공개 배포 전에는 QA 권한, 인증, 부하 제한, HTTPS, 감사 로그 정책을 다시 검토한다.
