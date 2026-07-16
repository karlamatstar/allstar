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
- AI Agent 실시간 채팅의 백그라운드 채점 완료 후 최신 Markdown·CSV·PNG 보고서 자동 갱신
- AI Agent 실시간 보고서의 상단 품질 요약 표·판정/항목점수/응답시간 그래프와 접이식 상세 목록
- A~D 설명과 질문별 프로필을 포함하는 VOC 실시간 Markdown 리포트
- `AI Agent QA AllStar` Streamlit 통합 화면의 AI 상담(AI Agent)·고객 의견 분석(VOC)·결과 보고서(Report)·상태 확인(Monitoring) 영역
- VOC 챗봇 A~D 카드와 실제 모델·추론 설정 표시
- Docker Compose의 Portfolio API, VOC API, VOC 에이전트 6개, Prometheus, Grafana
- Windows 호스트 통합 화면(Streamlit)을 함께 제어하는 서버 관리(Server Control Center)
- 서버 관리 GUI 정상·강제 종료 시 현재 프로젝트 서비스를 정리하는 독립 종료 감시기
- 서버 관리 GUI의 비동기 단일 상태 확인, Docker Desktop 자동 준비, 8501 포트 기반 잔류 Streamlit 정리
- 서버 관리 GUI의 고정 웹 바로가기 5개, 상태 아이콘, Docker 개별 시작 한국어 안내
- AI 상담 품질검사 8개 구분과 고객 의견 분석 품질검사를 제공하는 품질검사 관리(QA Control Center)
- QA 관리 GUI의 두 줄 탭 표기, 동일 선택·비선택 탭 크기, A~D 에이전트 교차 테스트 명칭
- QA 일반·무작위·한계·순간 급증 시험의 VU·실행시간 입력과 k6 환경변수 전달
- QA 각 시험의 목적·진행 방식·확인 항목·자동 결과 생성을 안내하는 개별 설명과 GUI 보고서 경로 숨김
- QA 전체 14개 탭 공통 실행 잠금, 비동기 중지, 구조화 실행 상태 로그, 실제 AI 테스트 기본 제외
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

### 화면 용어 표기 원칙

- GUI와 대시보드는 쉬운 한국어를 먼저 표시하고, 원래 전문용어는 괄호 안에 함께 적는다.
- 서비스 ID, API 경로, 환경변수, 모델명처럼 프로그램 동작에 필요한 내부 값은 변경하지 않는다.
- 모델 설정은 `답변 생성`, `독립 품질 평가(Judge)`, `추론 강도` 순서로 표시한다.
- 추론 설정은 `추론 끔(none)`, `낮음(low)`, `중간(medium)`, `높음(high)`처럼 한국어와 원래 값을 함께 표시한다.
- VOC A~D 프로필 카드는 같은 해상도에서 네 카드의 높이와 선택 버튼 위치가 모두 같아야 한다. 화면 폭이 좁아지면 네 카드가 동일한 반응형 높이로 함께 늘어나며, 내용이 높이를 넘을 때는 해당 카드 안에서만 스크롤한다.
- 주요 화면 용어는 다음 기준을 사용한다.

| 쉬운 화면 표기 | 원래 전문용어 | 뜻 |
|---|---|---|
| AI 상담 에이전트 | AI Agent | 사용자의 질문에 답변하는 기능 |
| 고객 의견 분석 | VOC | 고객의 소리와 의견을 검색·분석하는 기능 |
| 프로그램 연결 통로 | API | 화면과 서버가 데이터를 주고받는 연결 방식 |
| 독립 품질 평가 | Judge | 생성된 답변을 별도 모델이 채점하는 단계 |
| 통합 화면 | Streamlit | 챗봇·보고서·상태를 보는 웹 화면 |
| 서버 기능 명세 | Swagger | 서버가 제공하는 기능과 요청 형식을 확인하는 화면 |
| 운영 상태 화면 | Grafana | 수집된 운영 지표를 그래프로 보는 화면 |
| 상태 정보 수집 | Prometheus | 서버 상태와 성능 수치를 모으는 도구 |
| 실행 기록 | Log | 서비스 실행 과정과 오류를 남긴 기록 |

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
_OUTPUT/logs/qa/qa_runs.jsonl
_OUTPUT/logs/qa/runs/{test_id}/{run_id}.log
_OUTPUT/logs/qa/k6/{test_id}/{run_id}_summary.json
_OUTPUT/logs/services/
_OUTPUT/reports/manifests/
_OUTPUT/reports/manifests/qa/
_OUTPUT/reports/qa/latest/
_OUTPUT/reports/ai_agent/batch/
_OUTPUT/reports/ai_agent/batch/history/
_OUTPUT/reports/ai_agent/live/
_OUTPUT/reports/ai_agent/live/assets/
_OUTPUT/reports/voc/live/latest/voc_live_report.md
_OUTPUT/reports/voc/live/history/
_OUTPUT/reports/voc/testcase/a~d/
_OUTPUT/reports/voc/cross_validation/
_OUTPUT/reports/defects/chatbot/
_OUTPUT/reports/defects/chaos/
_OUTPUT/reports/performance/
```

원본 로그와 생성 리포트는 서로 다른 최상위 폴더에 저장한다. 실시간 리포트는 해당 서비스의 실시간 대화·채점 로그만 사용하며 테스트케이스 및 교차검증 결과와 섞지 않는다. 2026-07-16에 기존 `quality/reports/live_log/`, `quality/reports/testcase_log/` 사용을 종료하고 위 구조로 코드·화면·테스트 경로를 이전했다.

AI Agent 실시간 보고서는 사용자 답변을 반환한 뒤 백그라운드에서 두 답변의 채점 로그를 모두 저장하고 자동 갱신한다. 대화·채점 JSONL은 계속 누적하지만 보고서 Markdown·CSV·PNG는 최신본만 유지한다. 상단 요약 표와 그래프를 먼저 표시하고 FAIL·REVIEW·N/A 상세 및 최근 채팅 목록은 접기·펼치기로 제공한다. 세부 기준은 `AI_AGENT_LIVE_REPORT_AUTOMATION.md`를 따른다.

실행 코드가 리포트 폴더에 섞이지 않도록 챗봇 결함 기록기는 `src/allstar/ai_agent/evaluation/defect_logger.py`에 두고, Markdown 결과만 `_OUTPUT/reports/defects/chatbot/`에 저장한다. 성능 리포트 화면도 `_OUTPUT/reports/performance/`를 사용한다.

QA 관리 GUI의 14개 시험은 공통 실행 기록 자동화를 사용한다. 실행별 원문 로그와 k6 원본 요약은 누적하고, 시험별 실행 요약 Markdown과 전체 최신 실행 요약은 최근 결과로 덮어쓴다. 최신 manifest를 함께 갱신하므로 후속 통합 보고서 대시보드는 폴더 구조를 추측하지 않고 동일한 형식을 읽을 수 있다. 세부 기준은 `QA_REPORT_AUTOMATION.md`에 기록한다.

서버 연결 성능 종합 시험은 기존의 0초·20초·40초 예약 실행을 사용하지 않는다. `1명 → 10명 → 25명` 단계를 각각 별도의 k6 프로세스로 실행하고, 앞 단계가 끝난 뒤 5초간 안정화한 후 다음 단계를 시작한다. 원본 성능 데이터에는 단계 식별자를 직접 저장해 긴 응답이 발생해도 보고서의 단계별 결과가 섞이지 않게 한다.

공통 QA Markdown은 정식 품질 보고서가 아니라 실행 상태와 증적을 연결하는 보조 요약이다. VOC A~D 테스트케이스는 프로필 한 번 실행마다 TC-01·TC-02를 단일 Judge 프로세스로 처리하고, 실행 JSON 로그에서 프로필별 Markdown·CSV·JSON·PNG 그래프를 재생성한다. 프로필 결과가 2개 이상이면 A~D 종합 비교 보고서를 최신 결과로 갱신한다. 세부 기준은 `VOC_TESTCASE_REPORT_AUTOMATION.md`를 따른다.

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

### 화면 용어 한국어화 후 추가 검증

- 검증일: 2026-07-16
- 대상: 서버 관리 GUI, 품질검사 관리 GUI, 통합 Streamlit 화면, 기존 포트폴리오 대시보드
- `src`, `tools`, `tests` 전체 Python 문법 검사 통과
- 화면 용어 전용 통합 테스트를 포함한 `tests/integration` 13개 통과
- 실제 외부 AI 호출 테스트를 제외한 비AI 회귀 테스트 104개 통과, 2개 선택 제외
- 내부 서비스 ID, API 경로, 모델명은 변경하지 않음

### 서버 관리 종료 감시 추가 검증

- 검증일: 2026-07-17
- `src`, `tools`, `tests` 전체 Python 문법 검사 통과
- 서버 관리 종료 흐름을 포함한 통합 테스트 17개 통과
- 실제 외부 AI 호출 테스트를 제외한 비AI 회귀 테스트 108개 통과, 2개 선택 제외
- 실행 중인 서버를 실제로 종료하는 시험은 다른 작업에 영향을 줄 수 있어 수행하지 않고 종료 명령을 대체한 테스트로 검증

### 서버 관리 반응·시작 흐름 개선 검증

- 검증일: 2026-07-17
- Docker Desktop 실행 상태와 8501 포트 점유 상태를 읽기 전용으로 확인
- 상태 확인의 백그라운드·동시 실행과 단일 반복 예약 기준 확인
- Docker가 꺼진 조건의 자동 실행 및 준비 대기를 외부 실행 대체 테스트로 확인
- PID 기록이 없는 8501 포트 점유 Streamlit 종료를 외부 실행 대체 테스트로 확인
- 고정 웹 바로가기 5개, 상태 아이콘, 상단 버튼 순서, Docker 한국어 경고 기준 확인
- 기본·최소 창 크기, 중앙 배치, 좌우 영역 최소 폭 기준 확인
- 통합 테스트 23개 통과
- 실제 외부 AI 호출 테스트를 제외한 비AI 회귀 테스트 113개 통과, 2개 선택 제외
- 현재 실행 중인 8501 Streamlit은 사용 화면 중단을 피하기 위해 강제로 종료하지 않음

### QA 관리 GUI 탭 개선 검증

- 검증일: 2026-07-17
- 최상위·AI 시험·VOC 시험 탭의 두 줄 문자열을 Tkinter 숨김 생성으로 확인
- 선택·비선택 탭의 동일 여백 `(14, 9)` 적용 확인
- A~D 탭의 `에이전트 교차 테스트` 명칭과 둘째 줄 프로필 문자 확인
- 보고서 폴더 버튼 제거 확인
- 일반·무작위·한계·순간 급증 시험의 VU·실행시간 입력칸과 이전 GUI 기본값 확인
- 양의 정수 입력 검증과 `K6_VUS`, `SCRIPT_DURATION`, `TARGET_IP` 전달 기준 확인
- AI 시험 8개와 VOC 시험 6개의 개별 목적 설명 및 GUI 보고서 경로 미표시 확인
- QA 전체 탭 공통 실행 잠금, 실행·중지 버튼 상태 전환, 비동기 중지 확인
- 시작·완료·실패·사용자 중지 상태의 JSONL 기록 확인
- 장애·기능 검증 시험의 실제 AI 호출 파일과 `end_to_end` 기본 제외 확인
- 공통 누적 로그, 최신 실행 요약, VOC 단일 정식 보고서, 로그 재생성, PNG 그래프와 manifest 검증 포함 통합 테스트 42개 통과
- 실제 외부 AI 호출 테스트를 제외한 비AI 회귀 테스트 140개 통과, 2개 선택 제외

### 디렉터리 정렬 검증 참고

- 아래 디렉터리 정렬 검증 당시에는 실제 AI API를 호출하지 않았다. 이후 2026-07-17 보고서 자동화 검증에서 승인된 A 프로필 대표 2건을 별도로 실행했다.
- 기존 `voc/quality_diagnosis/test_mcp_tools.py` 전체 실행 중 3건은 이번 경로 변경과 무관한 기존 조건(`voc/main.py` 부재, 별도 로컬 에이전트의 CSV 경로, API 키 미설정)으로 실패했다.
- 경로 변경 대상 모듈과 비AI 회귀 묶음은 위에 기록한 16개 및 72개 테스트로 별도 통과를 확인했다.

### AI Agent 실시간 보고서 자동 갱신 검증

- 검증일: 2026-07-17
- 채팅 응답 후 두 모델의 백그라운드 채점 로그 저장과 최신 보고서 자동 갱신 순서를 확인
- 대화·채점 JSONL 누적과 Markdown·CSV·PNG 최신본 덮어쓰기 확인
- 상단 요약 표, 판정 분포·품질 항목 평균·응답시간 추이 PNG와 접이식 상세 목록 확인
- N/A·미채점을 FAIL과 분리하고 실제 채점 결과만 통과율·평균점수에 사용하는 기준 확인
- AI Agent 전용 비API 테스트 10개 통과
- 전체 비API 회귀 테스트 144개 통과, 환경 조건 3개 건너뜀, 실제 API 종단 테스트 2개 선택 제외
- 실제 OpenAI·Anthropic 답변·채점 API는 호출하지 않음

### 서버 연결 성능 단계별 독립 실행 검증

- 검증일: 2026-07-17
- 1명·10명·25명 단계가 서로 다른 k6 실행으로 순서대로 시작되는지 확인
- 단계 사이 5초 안정화 대기가 정확히 두 번 적용되는지 확인
- 고정 20초·40초 시작 예약이 제거됐는지 확인
- 시간 구간이 아니라 `phase1`·`phase2`·`phase3` 식별자로 보고서가 집계되는지 확인
- 관련 집중 테스트 24개 통과
- 실제 외부 AI 호출을 제외한 전체 비API 회귀 테스트 149개 통과, 2개 선택 제외
- 실제 성능 시험과 외부 AI API는 호출하지 않음

### 기본 회귀에서 실행하지 않는 테스트

- `tests/test_negative_cases.py`: 실제 OpenAI API 호출
- `tests/test_quality_pipeline.py`: 대표 2건 실제 OpenAI API 호출
- QA GUI의 VOC B~D 실제 API 호출

2026-07-17에 A 프로필 `TC-01`, `TC-02`를 승인 후 실행했다. OpenAI 생성 파이프라인은 완료됐으나 Anthropic 인증 오류로 독립 평가는 미평가됐다. 상세 결과는 `QA_REPORT_AUTOMATION.md`를 따른다.

## 6. 다음 작업 우선순위

상세 기준은 `REMAINING_WORK_PLAN.md`를 따른다.

1. QA 실행 안전성 보완: 구현 및 비AI 검증 완료
2. QA 보고서 자동 생성 통일: 구현 및 비AI 검증 완료
3. 통합 결과 보고서 대시보드 완성
4. 챗봇 대시보드 세부 개선
5. VOC·A~D 모니터링 화면 완성
6. A 프로필 대표 2건 독립 평가 재검증: Anthropic 키 정상화 후 진행

AWS 또는 외부 공개 배포 전에는 QA 권한, 인증, 부하 제한, HTTPS, 감사 로그 정책을 다시 검토한다.
