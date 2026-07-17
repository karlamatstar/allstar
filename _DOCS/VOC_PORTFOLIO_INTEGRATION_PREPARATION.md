# AI Agent Portfolio + VOC 통합 프로젝트 준비 문서

- 문서 상태: 확정 설계 기준 및 구현 추적 문서
- 작성일: 2026-07-16
- 기준 프로젝트:
  - `ai_agent_quality_portfolio`
  - `voc_upgrade`
- 참고 기준선:
  - `VOC`
- 중요: 이 문서는 최초 설계 요구사항을 보존하면서 현재 구현 여부를 함께 추적한다. 전체 최신 구현 상태는 `INTEGRATED_PROJECT_IMPLEMENTATION.md`와 `PROJECT_PROGRESS_CHECKLIST.md`를 우선 확인한다.

## 1. 프로젝트 목표

기존 AI Agent Quality Portfolio에 업그레이드된 VOC 멀티에이전트 기능을 통합한다.

최종 시스템은 다음 기능을 한 프로젝트에서 제공하는 것을 목표로 한다.

- 기존 교육과정 AI 챗봇 및 품질관리 기능 유지
- VOC 전용 챗봇 추가
- VOC 실시간 대화 저장 및 독립 LLM Judge 평가
- VOC 테스트케이스 A~D 교차검증
- 실시간 대화, 테스트케이스, 교차검증 리포트 분리
- Prometheus/Grafana 기반 VOC 운영 모니터링
- 기존 Docker Compose 운영 방식 확장
- 서버 전용 GUI와 QA 전용 GUI 분리
- 현재 개발 환경은 localhost 사용
- 추후 강의실 컴퓨터를 서버로 사용할 수 있는 구조 유지

## 2. 통합 위치에 대한 기본 전제

### 2.1 권장안

`D:\_Study_Project\_Total`을 새 통합 프로젝트 루트로 사용한다.

```text
D:\_Study_Project\
├─ ai_agent_quality_portfolio\   원본 참고용
├─ VOC\                          이전 구조 비교용
├─ voc_upgrade\                  최신 VOC 기준
└─ _Total\                       새 통합 프로젝트
```

이 방식을 권장하는 이유:

- 기존 3개 저장소를 원형 그대로 보존할 수 있다.
- 통합 중 발생하는 변경이 원본 프로젝트에 섞이지 않는다.
- 필요한 코드만 선별해 구조를 다시 정리할 수 있다.
- 수업 발표 시 원본과 통합 결과를 비교하기 쉽다.

### 2.2 통합 위치 확정

통합 작업 루트는 `D:\_Study_Project\_Total`로 확정한다. `ai_agent_quality_portfolio`, `VOC`,
`voc_upgrade`는 원본 참고·비교용으로 보존하고 통합 기능을 직접 추가하지 않는다.

## 3. 요구사항 재구성

### 3.1 포트폴리오 통합

- 기존 AI Agent 챗봇 기능을 유지한다.
- 챗봇은 정확히 2개, `AI Agent 챗봇`과 `VOC 챗봇`으로 유지한다.
- 기존 Streamlit 대시보드에 VOC 영역을 추가하고 사용자가 두 챗봇 중 하나를 명확히 선택한다.
- 하나의 입력창에서 질문 주제를 자동 판별해 두 서버로 분기하는 통합 챗봇은 만들지 않는다.
- 기존 Prometheus, Grafana, Docker Compose 구성을 확장한다.
- 기존 배치 리포트와 실시간 리포트 기능을 손상시키지 않는다.

### 3.2 VOC 챗봇

- `voc_upgrade`의 6개 에이전트를 사용한다.
- 사용자는 질문을 보내기 전에 A~D 중 하나의 모델 프로필을 선택한다.
- 기본 프로필은 생성 모델과 평가 모델이 서로 다른 제공자인 A로 한다.
- 선택한 프로필은 해당 질문 1건의 생성 파이프라인과 독립 Judge에 함께 적용하며 처리 중에는 변경할 수 없다.
- Retriever는 CSV 검색만 수행하므로 A~D 모델 변경 대상에서 제외한다.
- VOC 질문 1건마다 `Interpreter → Retriever → Summarizer → Evaluator → Critic → Improver`의 전체 파이프라인을 순서대로 통과한다.
- 중간 에이전트 결과를 바로 사용자 답변으로 보이지 않고, `Improver`가 완성한 최종 결과를 사용한다.
- 최종 결과에 대한 실시간 LLM Judge 채점까지 끝나야 해당 질문 처리를 완료한다.
- VOC 전용 질문만 처리한다.
- VOC와 관련 없는 질문은 일반 LLM 답변으로 우회하지 않는다.
- Retriever 결과가 0건이면 후속 생성 LLM을 호출하지 않는다.
- 사용자에게 고정된 범위 외 응답을 반환한다.
- VOC 데이터에 근거하지 않은 일반지식 답변을 하지 않는다.
- 초기 버전은 단발 질문 단위로 동작한다.
- 멀티턴 문맥은 별도 요구사항으로 분리한다.

권장 범위 외 응답:

```text
현재 등록된 VOC 데이터에서 관련 내용을 찾을 수 없습니다.
보험 VOC의 불편 사항, 원인 분석 또는 개선 방안과 관련된 질문을 입력해 주세요.
```

### 3.3 실시간 대화 품질평가

- 대시보드 VOC 챗봇에서 질문과 답변을 저장한다.
- 각 대화에 고유 `request_id`를 부여한다.
- 각 대화에 선택한 A~D 프로필, 생성·평가 제공자, 실제 모델명, 추론 강도를 함께 저장한다.
- 6개 에이전트의 최종 답변과 독립 LLM Judge 채점을 모두 완료한 뒤 사용자에게 답변과 채점 상태를 보여준다.
- 채점은 서버의 동일 요청 작업 안에서 이어지되지만, 중간 로그는 단계별로 즉시 저장한다.
- 질문, 검색 결과, 의도, 요약, 정책, trace, 단계별 시간, 채점 결과를 연결한다.
- API 실패는 FAIL이 아니라 N/A로 구분한다.
- 대화 원문과 채점 원문은 JSONL로 누적 저장한다.
- 누적된 채점 결과로 실시간 대화 품질 리포트를 생성한다.

### 3.4 테스트케이스 LLM Judge

- `voc_upgrade`의 테스트케이스와 9항목·100점 루브릭을 기준으로 한다.
- A~D 실험군을 각각 독립적으로 실행할 수 있어야 한다.
- 실행한 실험군만 해당 리포트를 생성한다.
- 재시도와 대체 모델을 끈 고정 조건을 유지한다.
- 실패는 0점으로 왜곡하지 않고 N/A로 기록한다.

### 3.5 교차검증 종합 리포트

- A~D 리포트 중 최소 2개가 존재할 때 생성 가능하도록 한다.
- 2개, 3개 또는 4개 결과를 자동 인식한다.
- 없는 실험군을 실패로 취급하지 않는다.
- 존재하는 실험군만 비교한다.
- 평균, 중앙값, N/A, 예외 PASS, 수행시간을 비교한다.
- 개별 테스트케이스 점수 차이를 함께 비교한다.

## 4. VOC 리포트 체계

VOC 리포트는 세 가지 계열로 분리한다. 이 분류는 기존 AI Agent 포트폴리오 리포트를 대체하지 않는다.

### 4.1 실시간 VOC 챗봇 리포트

데이터 원천:

- 실제 대시보드 VOC 대화 로그
- 대화별 독립 LLM Judge 결과
- 대화별 A~D 모델 프로필과 실제 호출 모델

특징:

- 운영 중 실제 사용 품질을 평가한다.
- 테스트케이스 리포트와 섞지 않는다.
- A~D 테스트케이스 리포트와 원본 데이터는 섞지 않는다.
- 원본 대화 로그를 다시 읽어 생성한다.
- 리포트 계열은 하나로 유지하되 A~D 프로필별 질문 수, 성공률, 점수, 처리시간을 필터링·비교할 수 있게 한다.
- 챗봇에서 A~D를 선택했다는 이유로 실시간 리포트를 네 계열로 분리하지 않는다.

리포트 맨 앞에는 해당 리포트가 사용한 실제 설정을 기준으로 A~D 설명표를 고정해서 넣는다.

| 프로필 | 의미 | 답변 생성 | 품질 평가 |
|---|---|---|---|
| A | 기본 교차 제공자 평가 | OpenAI `gpt-5.6-luna` | Anthropic `claude-sonnet-5` |
| B | 역방향 교차 제공자 평가 | Anthropic `claude-sonnet-4-6` | OpenAI `gpt-5.6-terra` |
| C | OpenAI 동일 제공자·분리 모델 | OpenAI `gpt-5.6-luna` | OpenAI `gpt-5.6-terra` |
| D | Anthropic 동일 제공자·분리 모델 | Anthropic `claude-sonnet-4-6` | Anthropic `claude-sonnet-5` |

리포트 생성 시 현재 환경변수 문자열을 그대로 복사하지 않고, 각 요청 로그에 저장된 실제 실행 모델을
집계한다. 기간 중 모델 설정이 변경됐다면 같은 프로필 안에서도 모델 버전별로 나누어 표시하고 변경 사실을
리포트 앞부분에 경고한다.

리포트 권장 순서:

1. 리포트 기간·생성 시각·전체 질문 수
2. A~D 의미와 생성·평가 모델·추론 강도 설명
3. A~D별 질문 수·성공률·평균 점수·평균 및 p95 처리시간 요약
4. 질문별 결과 요약
5. 질문별 7단계 결과와 Judge 상세
6. N/A·실패·취소 내역

질문별 결과 요약에는 최소한 다음 열을 포함한다.

| 필드 | 내용 |
|---|---|
| 요청 | `request_id`, 질문 시각 |
| 프로필 | A·B·C·D와 프로필 설명 |
| 질문·결과 | 질문 원문, 최종 답변 요약, 처리 상태 |
| 생성 설정 | 실제 생성 제공자·모델·추론 강도 |
| 평가 설정 | 실제 Judge 제공자·모델·추론 강도 |
| 품질 | 총점, 판정, N/A 사유 |
| 시간 | 파이프라인, Judge, 전체 처리시간 |

### 4.2 A~D 테스트케이스 리포트

교차검증 실험군마다 개별 리포트를 생성한다.

| 실험군 | 생성 제공자·모델 | 평가 제공자·모델 | 개별 리포트 |
|---|---|---|---|
| A | OpenAI · `gpt-5.6-luna` | Anthropic · `claude-sonnet-5` | A 리포트 |
| B | Anthropic · `claude-sonnet-4-6` | OpenAI · `gpt-5.6-terra` | B 리포트 |
| C | OpenAI · `gpt-5.6-luna` | OpenAI · `gpt-5.6-terra` | C 리포트 |
| D | Anthropic · `claude-sonnet-4-6` | Anthropic · `claude-sonnet-5` | D 리포트 |

사용자가 A만 실행하면 A 리포트만 생성한다. A와 C를 실행하면 A와 C 리포트가 각각 존재한다.

사용자가 GUI·대시보드에서 A~D 실험군을 실행하면 등록된 전체 테스트케이스를 하나의 실행과 하나의 정식 보고서로 합친다. 사례별 정식 보고서를 별도 폴더로 나누지 않는다. 실행 로그는 `run_id`별로 누적하고 프로필별 Markdown·CSV·JSON·그래프·manifest는 최신 실행으로 덮어쓴다. Codex 개발 검증은 별도 전체 실행 지시가 없으면 대표 `TC-01`, `TC-02`만 사용한다. 세부 구현 기준은 `VOC_TESTCASE_REPORT_AUTOMATION.md`를 따른다.

### 4.3 교차검증 종합 리포트

개별 A~D 리포트를 읽어 비교 결과를 만든다.

- A+B 비교 가능
- A+C+D 비교 가능
- A+B+C+D 전체 비교 가능
- 단일 실험군만 있을 때는 생성 버튼을 비활성화하거나 안내한다.

### 4.4 리포트 수 해석

- 실시간 VOC 챗봇 리포트: 1개 계열
- 테스트케이스 리포트: A~D 최대 4개
- 교차검증 종합 리포트: 1개 계열

따라서 리포트 종류는 3개 계열이며, 테스트케이스 리포트 내부에 최대 4개의 독립 실험 결과가 존재한다.

### 4.5 기존 AI Agent 포트폴리오 리포트 보존

기존 포트폴리오에 이미 구현된 다음 흐름은 통합 후에도 그대로 유지한다.

- AI Agent 챗봇 실시간 대화 로그
- 대화별 규칙 기반·API 기반 실시간 채점 로그
- 챗봇 실시간 대화 품질 리포트
- AI Agent 테스트케이스 배치 실행 로그
- 배치 평가 CSV·JSON·Markdown 리포트와 최신본
- 기존 검증·성능·결함 리포트

기존 생성기의 평가 로직은 재사용한다. 현재 구현은 `_OUTPUT/logs/ai_agent/`와 `_OUTPUT/reports/ai_agent/`를 사용한다.

## 5. 목표 디렉터리 구조

> 상태: **구조 기준 확정 및 실제 코드·폴더 이전 완료**

현재 구현은 아래 `src/allstar/`, `tools/`, `ops/`, `_OUTPUT/` 구조를 사용한다. 이전의 `app/`, `ai_quality/`, `voc/`, `voc_api/`, `logs/`, `quality/reports/` 최상위 경로는 제거했다.

최종 기준과 현재 경로별 상세 이동표는 `PROJECT_DIRECTORY_STRUCTURE.md`를 단일 기준 문서로 사용한다.

```text
_Total/
├─ src/allstar/
│  ├─ ai_agent/
│  │  ├─ api/
│  │  └─ evaluation/
│  ├─ voc/
│  │  ├─ api/
│  │  ├─ agents/
│  │  ├─ llm/
│  │  ├─ runtime/
│  │  ├─ mcp/
│  │  ├─ evaluation/
│  │  ├─ protocol/
│  │  └─ data/
│  ├─ ui/dashboard/
│  └─ shared/
├─ tools/
│  ├─ server_control/
│  ├─ qa_control/
│  └─ scripts/
├─ ops/
│  ├─ docker/
│  ├─ monitoring/
│  └─ performance/
├─ tests/
│  ├─ ai_agent/
│  ├─ voc/
│  └─ integration/
├─ RUN/                       더블클릭 실행 파일만 유지
├─ _OUTPUT/
│  ├─ logs/
│  └─ reports/
└─ _DOCS/
```

주요 결정은 다음과 같다.

- `quality/`, `ai_quality/` 이름을 없애고 평가 코드는 각 서비스의 `evaluation/`에 둔다.
- `app/`은 `src/allstar/ai_agent/api/`로 역할을 명확히 한다.
- `voc/`와 `voc_api/`를 `src/allstar/voc/` 아래에 결합한다.
- 공통 모델 프로필과 경로는 `src/allstar/shared/`에서 관리한다.
- `logs/`와 `quality/reports/`를 `_OUTPUT/logs/`, `_OUTPUT/reports/`로 결합한다.
- `_DOCS/`에는 기준 문서만 저장하고 자동 생성 리포트는 저장하지 않는다.
- 현재 실행 경로와 검증 결과는 `INTEGRATED_PROJECT_IMPLEMENTATION.md`를 따른다.

## 6. 서비스 아키텍처

### 6.1 전체 흐름

```text
Streamlit 통합 대시보드 :8501
  ├─ 기존 AI Agent 챗봇 → Portfolio FastAPI :8000
  └─ VOC 전용 챗봇      → VOC FastAPI Gateway :8100
                               ↓
                          gRPC Orchestrator
                               ↓
        Interpreter → Retriever → Summarizer → Evaluator → Critic → Improver
          :6001         :6002        :6003        :6004       :6005     :6006

Prometheus :9090
  ├─ Portfolio API /metrics
  └─ VOC API /metrics

Grafana :3000
  ├─ 기존 AI Agent 대시보드
  ├─ 기존 k6 대시보드
  └─ 신규 VOC 대시보드
```

### 6.2 VOC HTTP 게이트웨이

기존 AI Agent 포트폴리오는 이미 FastAPI HTTP 서버를 가지고 있다. 로컬 실행 시 `http://localhost:8000/docs`에서 Swagger API 문서를 확인할 수 있다.

여기서 신규로 제안한 VOC HTTP 게이트웨이는 기존 AI Agent API 앞에 또 하나의 중복 계층을 추가하는 것이 아니다. HTTP 진입점이 없는 VOC gRPC·MCP 파이프라인을 Streamlit, Prometheus, Docker와 연결하는 VOC 전용 FastAPI 서버다.

| 서버 | 역할 | 로컬 주소 | Swagger |
|---|---|---|---|
| Portfolio FastAPI | AI Agent 챗봇·채점·기존 기능 | `http://localhost:8000` | `http://localhost:8000/docs` |
| VOC FastAPI Gateway | VOC 6단계 파이프라인·최종 Judge·VOC 로그 | `http://localhost:8100` | `http://localhost:8100/docs` |

두 FastAPI를 분리하는 이유:

- Server Control Center에서 AI Agent 서버와 VOC 서버를 개별로 ON/OFF할 수 있다.
- VOC의 장시간 7단계 처리가 AI Agent 챗봇 서버의 응답성과 장애 범위에 영향을 주지 않는다.
- 각 서비스의 로그·메트릭·환경변수·Docker 상태를 분리할 수 있다.
- 수업 발표 중 한쪽에 문제가 생겨도 다른 챗봇을 계속 시연할 수 있다.

따라서 현재 권장안은 `FastAPI가 2개`이며, 추가 중계 서버까지 포함한 3개 구조가 아니다. 통합 대시보드가 각각 `:8000`과 `:8100`을 직접 호출한다. 추후 실제 서버 배포에서 하나의 주소만 노출해야 하면 리버스 프록시로 `/api/portfolio` 및 `/api/voc`를 묶을 수 있지만, 현재 로컬·수업 범위에서는 추가하지 않는다.

예상 API:

| 메서드 | 경로 | 목적 |
|---|---|---|
| GET | `/health` | VOC API 및 에이전트 상태 |
| GET | `/agents/health` | 6개 에이전트 개별 상태 |
| POST | `/chat` | VOC 전용 질문 분석 |
| GET | `/chat/{request_id}/status` | 처리 단계·경과 시간·완료 여부 조회 |
| GET | `/metrics` | Prometheus 지표 |
| POST | `/reports/live/generate` | 실시간 대화 리포트 생성 |
| GET | `/reports/live/latest` | 최신 실시간 리포트 조회 |
| POST | `/qa/testcase/{experiment}` | A~D 테스트 실행 요청 |
| POST | `/reports/cross-validation/generate` | 존재하는 A~D 결과 비교 |

장시간 테스트케이스 실행은 HTTP 요청을 오래 유지하기보다 QA GUI가 로컬 프로세스로 실행하거나 작업 상태 API를 별도로 두는 방식이 안전하다.

## 7. VOC 전용 챗봇의 범위 제한

### 7.1 처리 허용 범위

- VOC 데이터 검색
- 고객 불편 요약
- 공통 원인 분석
- 고객 영향 분석
- 개선안 생성
- 처리 우선순위
- 고객 안내 정책

### 7.2 처리 거부 범위

- 날씨, 뉴스, 일반 상식
- VOC 데이터와 무관한 상품 추천
- 개인적인 대화
- 등록되지 않은 실제 고객 개인정보 조회
- VOC 검색 결과가 없는 주제

### 7.3 안전한 처리 순서

```text
사용자 질문
  → 입력 기본 검증
  → Interpreter
  → Retriever
  → 검색 결과 0건 여부 확인
      ├─ 0건: 고정 범위 외 응답, 생성 LLM 중단
      └─ 1건 이상: 요약·평가·비평·개선 파이프라인 실행
```

### 7.4 프롬프트 원칙

- 검색된 VOC 원문만 사실 근거로 사용한다.
- 검색 데이터에 없는 수치와 정책을 사실처럼 확정하지 않는다.
- 개선안의 담당 부서, 기한, 정량 기준은 제안임을 명시한다.
- 개인정보를 요구하지 않는다.
- 원인과 개선안을 사실과 제안으로 구분한다.
- 모호한 질문은 특정 장애를 단정하지 않는다.

### 7.5 실시간 챗봇의 동적 검색어 생성

테스트 케이스와 실제 챗봇은 검색어를 다르게 다룬다.

- 테스트 케이스의 미리 정한 검색어·기대 결과는 Retriever가 올바르게 찾는지 검증하는 기준이다.
- 실제 VOC 챗봇에는 미리 정한 질문별 검색어를 요구하지 않는다.
- Interpreter가 매 질문을 분석해 `task`, 핵심 키워드, 복합 검색어, 최대 검색 건수를 동적으로 생성한다.
- 규칙 기반 키워드 추출기를 안전망으로 함께 사용해 LLM 출력이 비거나 흔들릴 때를 보완한다.
- Retriever는 원문 핵심어 복수 일치를 우선하고, 0건일 때만 동의어·표현 변형을 제한적으로 확장한다.
- 검색 결과는 일치한 핵심어 수와 구체성을 기준으로 정렬하여 범용어 하나만 겹치는 VOC가 상위에 오르지 않게 한다.
- 1단계 Interpreter 카드에서 자동 생성된 검색어를, 2단계 Retriever 카드에서 실제 사용한 검색어·확장어·검색 결과를 확인할 수 있게 한다.

실시간 챗봇에서는 다음 안전 규칙을 추가로 적용한다.

- 검색어 추출에 실패했다고 `상담`, `대기`, `지연`, `불친절`처럼 질문과 무관한 기본 검색어를 임의로 넣지 않는다.
- 검색어가 비었다고 자동으로 CSV 전체를 검색 결과로 반환하지 않는다.
- 사용자가 `전체 VOC를 요약해줘`처럼 전체 분석 의도를 명시한 경우에만 제한된 수의 전체 표본 검색을 허용한다.
- 질문이 모호하거나 검색어를 안전하게 생성할 수 없으면 엉뚱한 VOC를 사용하지 말고 사용자에게 주제를 더 구체적으로 입력해 달라고 안내한다.
- 최종 LLM Judge는 생성된 검색어 그 자체만 보지 않고, 원본 질문과 실제로 검색된 VOC가 의미적으로 관련되는지를 채점한다.

## 8. 실시간 로그와 채점 데이터

### 8.1 대화 로그 예시 필드

```json
{
  "request_id": "uuid",
  "timestamp": "ISO-8601",
  "model_profile": {
    "id": "A",
    "name": "기본 교차 제공자 평가",
    "generation": {
      "provider": "openai",
      "model": "gpt-5.6-luna",
      "reasoning": "none"
    },
    "judge": {
      "provider": "anthropic",
      "model": "claude-sonnet-5",
      "effort": "low",
      "thinking": "disabled"
    }
  },
  "question": "사용자 질문",
  "answer": "사용자에게 보인 최종 응답",
  "summary": "요약 결과",
  "policy": "정책 개선안",
  "intent": {},
  "retrieval_count": 0,
  "trace": "단계 추적",
  "stage_timings": {},
  "total_seconds": 0.0,
  "status": "success|no_data|error"
}
```

### 8.2 채점 로그 예시 필드

```json
{
  "request_id": "uuid",
  "timestamp": "ISO-8601",
  "profile_id": "A",
  "profile_snapshot": {
    "generation_provider": "openai",
    "generation_model": "gpt-5.6-luna",
    "generation_reasoning": "none",
    "judge_provider": "anthropic",
    "judge_model": "claude-sonnet-5",
    "judge_effort": "low",
    "judge_thinking": "disabled"
  },
  "judge_provider": "anthropic",
  "judge_model": "claude-sonnet-5",
  "criteria": {},
  "total_score": 0,
  "verdict": "배포 가능|조건부|개선 필요|보류|N/A",
  "summary": "채점 근거",
  "judge_seconds": 0.0,
  "status": "success|na|error"
}
```

### 8.3 저장 원칙

- 대화 로그와 채점 로그는 별도 JSONL 파일로 저장한다.
- `request_id`로 두 로그를 결합한다.
- A~D 프로필은 문자만 저장하지 않고 요청 시작 시점에 확정된 제공자·모델·추론 설정의 불변 스냅샷을 함께 저장한다.
- 서버 실행 중 환경변수나 중앙 프로필 설정이 바뀌어도 이미 시작된 요청 로그의 프로필 스냅샷은 변경하지 않는다.
- 대화 로그, 채점 로그, 서비스 실행 로그에 동일한 `request_id`와 `profile_id`를 기록한다.
- 채점 실패로 대화 로그를 잃지 않는다.
- 비밀키와 전체 시스템 프롬프트는 저장하지 않는다.
- 긴 원본 검색 결과는 보고서에 전부 복제하지 않고 필요한 미리보기와 참조만 남긴다.

### 8.4 리포트 원본 로그 자동 생성

- 사용자가 로그 파일을 따로 만들지 않아도 대화, 채점, 테스트, 교차검증 실행 시점에 `_OUTPUT/logs/`에 자동 생성한다.
- 실시간 VOC 리포트는 `_OUTPUT/logs/voc/live/conversations/`과 `_OUTPUT/logs/voc/live/judgments/`를 원천으로 삼는다.
- 실시간 리포트 manifest에는 사용한 로그 목록과 함께 A~D별 요청 수, 실제 모델 조합, 추론 설정을 기록한다.
- A~D 개별 리포트는 각각 `_OUTPUT/logs/voc/testcase/a/`~`d/`에 있는 해당 실험군의 실행 로그만 사용한다.
- 교차검증 종합 리포트의 원본은 `_OUTPUT/logs/voc/cross_validation/`에 비교 대상 A~D, 입력 파일, 집계 결과를 남긴다.
- 각 리포트 생성 시 `_OUTPUT/reports/manifests/`에 manifest JSON을 자동 생성하여 리포트 ID, 생성 시각, 사용한 로그 파일, 기간, 테스트 조합, 모델을 추적한다.
- 로그 파일명은 날짜와 실행 ID를 포함한다. 예: `2026-07-16_run-<uuid>.jsonl`.
- 실행 중에는 로그를 즉시 append하여 프로세스가 중단되어도 이미 처리한 결과를 복구할 수 있게 한다.
- 리포트는 변경 가능한 현재 상태를 직접 읽지 않고, 생성 시점에 확정된 로그와 manifest를 기준으로 만든다.

### 8.5 서비스 실행 로그

- 포트폴리오 API, VOC API, 6개 에이전트, Streamlit, Prometheus, Grafana, Server GUI, QA GUI의 표준 출력·오류를 `_OUTPUT/logs/services/<service-name>/`에 자동 저장한다.
- VOC 요청 관련 서비스 로그는 각 단계 시작·완료·실패 줄에 `request_id`, `profile_id`, 실제 모델명을 포함한다.
- Server GUI의 터미널은 이 서비스 로그를 실시간으로 보여준다.
- 실행 로그는 리포트 점수 계산에 직접 섞지 않고, 실패 원인과 실행 상태를 추적하는 용도로 사용한다.

### 8.6 AI Agent 로그·리포트 동일 적용

- AI Agent 챗봇 요청 시 `_OUTPUT/logs/ai_agent/live/conversations/`에 대화를 즉시 자동 저장한다.
- 동일 대화의 실시간 채점은 `_OUTPUT/logs/ai_agent/live/judgments/`에 저장하고 `request_id`로 연결한다.
- AI Agent 실시간 리포트는 위 두 로그만 읽으며, 두 모델의 백그라운드 채점 로그 저장 직후 최신 Markdown·CSV·PNG로 자동 갱신한다.
- AI Agent 실시간 보고서는 상단에 요약 표와 판정·품질점수·응답시간 그래프를 표시하고, FAIL·REVIEW·N/A 상세와 최근 채팅 목록은 접기·펼치기로 제공한다.
- 실시간 대화·채점 로그는 누적하고 보고서는 최신본만 유지한다. 수동 재생성은 자동 갱신 실패 시 사용하는 보조 기능이다.
- AI Agent 테스트케이스 실행 시 케이스별 입력·응답·채점·오류·수행시간을 `_OUTPUT/logs/ai_agent/testcase/`에 자동 저장한다.
- AI Agent 테스트케이스 리포트는 해당 실행 ID의 확정된 로그에서 생성하며, 최신본과 시간별 이력본을 모두 남긴다.
- AI Agent 리포트도 VOC와 동일하게 `_OUTPUT/reports/manifests/`에 사용한 로그 목록을 남긴다.
- 이 변경은 저장 위치와 추적성을 정리하는 것이며, 기존 평가 기준·화면·리포트 내용을 임의로 바꾸지 않는다.

## 9. Streamlit 통합 대시보드

### 9.1 최상위 영역

```text
1. AI Agent
2. VOC
3. 통합 모니터링
4. 통합 리포트
```

기존 대시보드 구조를 과도하게 변경하지 않고 VOC 최상위 탭을 추가하는 방식이 우선이다.

챗봇 진입 화면에서는 다음 두 가지만 제공한다.

```text
[ AI Agent 챗봇 ]   [ VOC 챗봇 ]
```

- `AI Agent 챗봇`은 기존 Portfolio FastAPI `:8000`만 호출한다.
- `VOC 챗봇`은 신규 VOC FastAPI Gateway `:8100`만 호출한다.
- 각 챗봇의 화면 상태, 대화 기록, 채점 상태, 로그, 리포트 버튼을 분리한다.
- 한 챗봇의 대화나 평가 결과를 다른 챗봇의 리포트 입력으로 사용하지 않는다.

### 9.2 VOC 영역 탭

- VOC 챗봇
- 실시간 대화 로그
- 실시간 품질 현황
- 실시간 리포트
- 테스트케이스 A~D
- 교차검증 비교
- VOC Grafana

### 9.3 VOC 챗봇 화면

- 사용자 질문 입력
- 답변 말풍선
- 검색 건수
- 처리시간
- A~D 모델 프로필 선택과 생성·평가 모델 조합 표시
- 범위 외 질문 안내
- 질문을 전송하면 해당 세션을 `processing`으로 설정하고 입력창과 전송 버튼을 비활성화한다.
- 처리 중에는 `생각 중… 37초 경과`처럼 시작 시점부터의 경과 시간을 1초 단위로 계속 갱신한다.
- 가능하면 `의도 분석 중`, `VOC 검색 중`, `요약 중`, `평가 중`, `비판 중`, `최종 개선 중`, `LLM Judge 채점 중`의 현재 단계도 함께 표시한다.
- 6개 에이전트와 LLM Judge가 모두 완료되기 전에는 최종 답변을 화면에 노출하지 않는다.
- 완료 시 최종 답변, 채점 요약, 총 처리 시간을 함께 표시하고 입력을 다시 활성화한다.
- 실패·시간 초과·사용자 취소 시에도 상태와 저장된 단계까지를 안내한 후 입력을 다시 활성화한다.
- 한 브라우저 세션에서 동시 VOC 질문은 1건만 허용한다.

### 9.3.1 A~D 모델 프로필 선택

질문 입력창 위에 A~D 프로필 카드를 가로로 배치한다. 프로필 문자는 단순한 실험 번호가 아니라
`누가 답변을 만들고 누가 독립적으로 평가하는지`를 선택하는 실행 설정이다.

| 프로필 | 화면 설명 | 생성 파이프라인 | 독립 Judge | 용도 |
|---|---|---|---|---|
| A | OpenAI 생성 + Anthropic 평가 | `gpt-5.6-luna` · 추론 없음 | `claude-sonnet-5` · low | 기본 권장. 서로 다른 회사 모델로 답변과 평가를 분리 |
| B | Anthropic 생성 + OpenAI 평가 | `claude-sonnet-4-6` · low | `gpt-5.6-terra` · low | A의 역할을 반대로 바꿔 교차 평가 방향 비교 |
| C | OpenAI 계열 생성·평가 | `gpt-5.6-luna` · 추론 없음 | `gpt-5.6-terra` · low | OpenAI 안에서 빠른 생성 모델과 강한 평가 모델을 분리 |
| D | Anthropic 계열 생성·평가 | `claude-sonnet-4-6` · low | `claude-sonnet-5` · low | Anthropic 안에서 생성 모델과 평가 모델을 분리 |

사용자 안내 문구:

```text
A~D는 답변 생성 모델과 품질 평가 모델의 조합입니다.
A는 OpenAI가 답변을 만들고 Anthropic이 독립 평가하는 기본 권장 조합입니다.
선택한 조합은 현재 질문 1건에 적용되며, 테스트케이스 전체를 실행하지 않습니다.
```

카드 표시 예시:

```text
[A · 기본 권장]
답변 생성  OpenAI / gpt-5.6-luna / 추론 없음
품질 평가  Anthropic / claude-sonnet-5 / low
서로 다른 제공자 교차 평가
```

선택 동작:

- 최초 진입 시 A를 선택한다.
- 선택한 카드는 색상·테두리·체크 표시로 명확하게 강조한다.
- 카드를 선택하면 바로 아래에 조합 설명, 장점, 실제 모델명, 추론 설정을 표시한다.
- 사용 가능한 API 키가 없는 프로필은 비활성화하고 부족한 제공자 설정을 안내한다.
- 질문 전송 시 선택값을 복사해 요청에 고정하고, 7단계 처리 중에는 프로필 변경을 막는다.
- 처리가 끝난 뒤 다음 질문부터 다른 프로필을 선택할 수 있다.
- 브라우저 세션에서는 마지막 선택값을 유지하되 항상 현재 선택 프로필을 질문 입력창 가까이에 표시한다.
- 서버가 임의로 다른 제공자나 모델로 대체하지 않는다. 생성 실패는 해당 프로필 실패로 표시하고,
  Judge만 실패한 경우 생성된 답변은 보여주되 품질 점수는 N/A로 표시한다.
- 챗봇 A~D 선택은 질문 1건의 모델 프로필만 바꾸며, QA 탭의 A~D 테스트케이스 배치 실행을 시작하지 않는다.
- 챗봇과 QA가 동일한 중앙 `MODEL_PROFILES` 설정을 읽어 모델명과 추론 강도가 서로 달라지지 않게 한다.

### 9.3.2 7단계 처리 트래커

VOC 챗봇 대화 영역 바로 아래에 6개 에이전트와 최종 Judge를 포함한 7개의 사각형 단계 카드를 화살표로 연결해 표시한다.

```text
[① 의도 분석] → [② VOC 검색] → [③ 요약] → [④ 평가] → [⑤ 비판] → [⑥ 최종 개선] → [⑦ LLM Judge]
 Interpreter       Retriever       Summarizer    Evaluator     Critic       Improver          최종 채점
```

각 카드는 다음 상태를 색상과 아이콘으로 함께 구분한다. 색상만으로 상태를 구분하지 않는다.

| 상태 | 표시 예 | 의미 |
|---|---|---|
| 대기 | `○ 대기` + 회색 | 아직 시작하지 않음 |
| 진행 | `◔ 처리 중` + 파란색 강조/애니메이션 | 현재 실행 중인 단계 |
| 완료 | `✓ 완료` + 초록색 | 정상 종료 |
| 건너뜀 | `– 건너뜀` + 연한 회색 | 검색 0건 등으로 후속 단계 미실행 |
| 실패 | `! 실패` + 빨간색 | 오류 또는 시간 초과 |

- 상단에 `생각 중… 37초 경과`를 고정 표시한다.
- 각 완료 카드에 해당 단계의 수행 시간을 표시한다. 예: `✓ 완료 · 2.8초`.
- 활성 카드는 자동으로 다음 카드로 이동하며, 완료된 카드는 완료 상태를 유지한다.
- 화면 너비가 부족한 경우 7개를 압축하거나 세로로 쌓지 않고, 위 상태 카드와 아래 결과 버튼을 같은 폭으로 정렬한 공통 가로 스크롤을 사용한다.
- 사용자에게 내부 프롬프트나 사고 내용을 노출하지 않고, 단계명·상태·수행 시간만 보여준다.

### 9.3.3 단계별 결과 상세 보기

7개 단계 카드는 선택 가능한 탭·버튼처럼 동작한다. 사용자가 완료된 카드를 선택하면 트래커 아래의 공통 상세 패널에 해당 단계가 실제로 생성하여 다음 단계에 전달한 결과를 보여준다.

| 선택 단계 | 상세 패널에 표시할 내용 |
|---|---|
| ① Interpreter | 분류된 의도, 핵심 키워드, 질문 범위, VOC 관련 여부 |
| ② Retriever | 검색 건수, 선택된 VOC 항목, 유사도·참조 정보 |
| ③ Summarizer | 검색된 VOC의 핵심 요약 |
| ④ Evaluator | 품질 평가 결과, 점수, 판정 근거 |
| ⑤ Critic | 부족한 점, 위험, 추가 개선 요구사항 |
| ⑥ Improver | 사용자에게 제공할 최종 개선 답변 |
| ⑦ LLM Judge | 항목별 점수, 총점, 판정, 채점 근거 |

- `완료` 카드는 즉시 선택할 수 있다.
- `진행 중` 카드를 선택하면 상세 패널에 처리 중임을 표시하고, 미완성 출력은 노출하지 않는다.
- `대기`나 `건너뜀` 카드는 비활성화하거나 건너뛴 이유만 보여준다.
- 새 질문을 시작하면 상세 패널도 해당 `request_id`의 데이터로 초기화하여 이전 질문의 단계 결과와 섞이지 않게 한다.
- 이전 대화를 선택하면 해당 대화의 7단계 상태와 결과도 다시 조회할 수 있게 로그에 보존한다.
- 상세 패널은 원본 시스템 프롬프트, 비밀키, 모델의 내부 사고 과정을 노출하지 않고 명시적으로 생성된 단계 출력만 보여준다.

### 9.4 리포트 화면

- 기존 포트폴리오의 AI 상담 챗봇·검증·성능·테스트케이스 보고서 4개를 보존한다.
- 상위 `리포트 모음` 탭 아래에 신규 VOC 챗봇 보고서와 VOC A~D 테스트케이스 보고서를 추가해 총 6개 보고서 하위 탭을 사용한다.
- VOC A~D는 하나의 보고서 하위 탭 안에서 `교차 테스트 (A)`부터 `교차 테스트 (D)`까지의 개별 결과와 종합 비교를 선택한다.
- 존재하는 A~D 결과만 활성화하고 실행하지 않은 프로필은 실패로 표시하지 않는다.
- 2개 이상일 때 교차검증 종합 리포트를 표시하거나 선택할 수 있게 한다.
- 최신 보고서를 대시보드 본문에 표시하고 누적 원본 로그는 별도로 유지한다.
- 세부 화면 요구사항은 `INTEGRATED_REPORT_DASHBOARD_REQUIREMENTS.md`를 따른다.

## 10. Prometheus 및 Grafana

### 10.1 Prometheus 수집 대상

- 기존 Portfolio API `app:8000/metrics`
- 신규 VOC API `voc-api:8100/metrics`

### 10.2 권장 VOC 메트릭

| 메트릭 | 라벨 | 의미 |
|---|---|---|
| `voc_chat_requests_total` | status | 전체 VOC 질문 수 |
| `voc_chat_latency_seconds` | - | 사용자 응답시간 |
| `voc_active_requests` | - | 현재 처리 중인 VOC 질문 수 |
| `voc_pipeline_latency_seconds` | - | 6개 에이전트 전체 시간 |
| `voc_stage_latency_seconds` | stage | 에이전트별 처리시간 |
| `voc_agent_requests_total` | agent,status | 에이전트 호출 결과 |
| `voc_retrieval_results` | - | 질문별 검색 건수 |
| `voc_no_data_total` | - | 관련 데이터 없음 건수 |
| `voc_query_expansion_total` | method,status | 동의어·표현 확장 사용 결과 |
| `voc_out_of_scope_total` | - | VOC 범위 외 질문 수 |
| `voc_llm_calls_total` | provider,agent,status | LLM 호출 결과 |
| `voc_llm_retries_total` | provider,agent | 재시도 횟수 |
| `voc_live_judge_total` | provider,verdict | 실시간 채점 분포 |
| `voc_live_judge_score` | criterion | 실시간 평가 항목 점수 |
| `voc_live_judge_latency_seconds` | provider | 최종 Judge 채점 시간 |
| `voc_testcase_runs_total` | experiment,status | A~D 실행 결과 |
| `voc_testcase_score` | experiment,criterion | A~D 평균 및 항목별 점수 |
| `voc_testcase_duration_seconds` | experiment | A~D 실행 소요시간 |
| `voc_testcase_na_total` | experiment | A~D 채점 불가 횟수 |

토큰 사용량을 SDK 응답에서 얻을 수 있는 경우 다음 메트릭을 추가할 수 있다.

- `voc_llm_input_tokens_total`
- `voc_llm_output_tokens_total`
- `voc_llm_reasoning_tokens_total`

### 10.3 VOC Grafana 화면

기존 `AI Agent 발표용 운영 모니터링`과 `K6 Performance Test` Grafana 대시보드는 유지한다. VOC는 운영 흐름과 QA 결과를 한 화면에 섞지 않고 두 개의 대시보드로 나눈다.

#### 10.3.1 VOC 실시간 운영 대시보드

| 행 | 패널 | 표현 형식 | 확인 목적 |
|---|---|---|---|
| 1 | 누적 질문 수 | Stat | 전체 사용량 |
| 1 | 성공률 | Gauge/Stat | 정상 완료 비율 |
| 1 | 현재 처리 중 | Stat | 동시 진행 작업 수 |
| 1 | 평균 총 응답시간 | Stat | 사용자 체감 속도 |
| 1 | p95 총 응답시간 | Stat | 느린 요청 감지 |
| 1 | 최근 Judge 평균 점수 | Gauge | 최근 응답 품질 |
| 2 | 시간별 요청·실패 추이 | Time series | 특정 시간대 장애 확인 |
| 2 | 총 응답시간 p50/p90/p95 | Time series | 속도 추이 확인 |
| 3 | 7단계별 평균·p95 시간 | 가로 Bar chart | 어느 에이전트나 Judge가 병목인지 확인 |
| 3 | 에이전트별 성공·실패·시간 초과 | Stacked bar | 단계별 안정성 |
| 4 | 평균 검색 건수 | Stat/Time series | Retriever 결과 규모 |
| 4 | 검색 0건 비율 | Gauge | 검색 누락 또는 범위 외 질문 증가 |
| 4 | 동의어 확장 사용률 | Time series | 1차 검색의 취약성 |
| 4 | 범위 외 질문 비율 | Stat | VOC 전용 제한 동작 |
| 5 | Judge 판정 분포 | Pie/Bar chart | 배포 가능·조건부·개선 필요·N/A 비율 |
| 5 | Judge 항목별 평균 점수 | Bar chart | 정확성·근거성·관련성 등 취약 항목 |
| 5 | Judge 채점 소요시간 | Time series | 최종 채점 병목 |
| 6 | VOC API·6개 에이전트·Prometheus 상태 | State timeline/Status history | 서비스 상태 |
| 6 | OpenAI/Anthropic 호출 성공·실패·재시도 | Stacked bar | 제공자별 장애 및 재시도 |

발표 시에는 1~3행만 보여도 `현재 정상인지`, `어느 단계가 느린지`를 즉시 설명할 수 있다.

#### 10.3.2 VOC QA·A~D 테스트 대시보드

| 패널 | 표현 형식 | 확인 목적 |
|---|---|---|
| 최근 A/B/C/D 총점 | Grouped bar | 모델 조합별 품질 비교 |
| A~D 실행 상태 | Status table | 성공·실패·취소·N/A |
| A~D 소요시간 | Bar chart | 조합별 속도 비교 |
| A~D 항목별 평균 점수 | Heatmap | 어느 조합이 어느 평가 항목에 강한지 확인 |
| PASS·FAIL·N/A 분포 | Stacked bar | 실험군별 결과 분포 |
| 테스트 실행 이력 | Time series | 개선 전후 점수·시간 변화 |

QA 실행 프로세스는 종료 후 사라지므로, 종료 시 A~D 집계 결과를 VOC API의 전용 등록 경로로 전달하거나 Pushgateway를 사용해 Prometheus가 수집할 수 있게 한다. 통합 초기에는 별도 서비스를 추가하지 않도록 VOC API가 QA 완료 집계를 받아 메트릭으로 노출하는 방식을 우선한다.

Grafana는 운영·QA 집계를 보여주는 화면으로 제한한다. 질문 원문, 고객 내용, 에이전트 출력, `request_id`, 시스템 프롬프트는 Prometheus 라벨이나 Grafana 패널에 넣지 않는다. 이런 상세 내용은 통합 대시보드의 7단계 상세 패널과 로그·리포트에서만 조회한다.

통합 Streamlit에는 기존 포트폴리오의 Grafana 탭을 확장한 상위 `모니터링` 탭을 하나 두고, 선택하면 기존 2개와 신규 VOC 2개가 총 4개 하위 탭으로 바로 표시되게 한다. 중간 탭을 추가하지 않는다. 화면 구조, UID, 빈 상태와 완료 기준은 `INTEGRATED_GRAFANA_DASHBOARD_REQUIREMENTS.md`를 따른다. 2026-07-17에 VOC Grafana JSON 2개와 통합 화면 코드를 구현했으며, 실제 Docker 프로비저닝과 실데이터 패널 검증은 남아 있다.

## 11. Docker Compose 계획

### 11.1 기존 서비스 유지

- `app`: 기존 Portfolio FastAPI
- `prometheus`
- `grafana`

### 11.2 신규 서비스

- `voc-api`
- `voc-interpreter`
- `voc-retriever`
- `voc-summarizer`
- `voc-evaluator`
- `voc-critic`
- `voc-improver`

결정 완료: 서버 서비스는 Docker로 실행하고 Streamlit은 Windows 호스트 프로세스로 실행한다.
Server Control Center가 Docker 서비스와 호스트 Streamlit을 한 화면에서 함께 시작·종료하며,
Streamlit 행의 접속 버튼으로 `http://localhost:8501`을 연다. 추후 완전한 Docker 배포가 필요하면
Streamlit 컨테이너화를 별도 변경으로 검토한다.

### 11.3 Docker 내부 엔드포인트

컨테이너에서는 `localhost`가 아니라 Compose 서비스명을 사용한다.

```text
INTERPRETER_ENDPOINT=voc-interpreter:6001
RETRIEVER_ENDPOINT=voc-retriever:6002
SUMMARIZER_ENDPOINT=voc-summarizer:6003
EVALUATOR_ENDPOINT=voc-evaluator:6004
CRITIC_ENDPOINT=voc-critic:6005
IMPROVER_ENDPOINT=voc-improver:6006
```

호스트에서 직접 실행할 때는 기존처럼 `localhost:6001~6006`을 사용한다.

### 11.4 볼륨

- AI Agent 기존 보고서
- VOC 실시간 로그
- VOC A~D 테스트케이스 보고서
- VOC 교차검증 보고서
- 필요한 실행 로그

보고서와 로그는 컨테이너 삭제 후에도 호스트에 남도록 바인드 마운트한다.

## 12. 포트 계획

| 서비스 | 포트 | 상태 |
|---|---:|---|
| Portfolio FastAPI | 8000 | 기존 유지 |
| Streamlit Dashboard | 8501 | 기존 유지 |
| VOC FastAPI Gateway | 8100 | 신규 |
| Interpreter gRPC | 6001 | 기존 유지 |
| Retriever gRPC | 6002 | 기존 유지 |
| Summarizer gRPC | 6003 | 기존 유지 |
| Evaluator gRPC | 6004 | 기존 유지 |
| Critic gRPC | 6005 | 기존 유지 |
| Improver gRPC | 6006 | 기존 유지 |
| Prometheus | 9090 | 기존 유지 |
| Grafana | 3000 | 기존 유지 |

현재 개인 컴퓨터에서는 모든 사용자 접속 주소를 `127.0.0.1` 또는 `localhost`로 사용한다.

강의실 서버 전환 시에는 클라이언트에서 서버 IP만 변경하고 Docker 내부 서비스명은 유지하는 구조로 만든다.

## 13. 서버 전용 GUI

별도의 `Server Control Center`를 만든다.

### 13.1 목적

- 모든 서버 전체 시작·종료
- 개별 서버 시작·종료
- 서버 상태 표시
- 서비스별 로그 확인
- 대시보드, Swagger, Prometheus, Grafana 바로 열기

### 13.2 관리 대상

- Portfolio API
- Streamlit
- VOC API
- VOC 에이전트 6개
- Prometheus
- Grafana

### 13.3 화면 구조

초기 구현은 서비스 목록과 선택 서비스 전용 로그 화면을 조합한다. 실제 화면을 사용해 본 뒤
오류 요약, 다중 로그 보기 또는 배치 개선이 필요한지 다시 판단한다.

```text
상단: [전체 시작] [전체 종료] [상태 새로고침]

왼쪽: 서비스 목록과 상태
  ● Portfolio API
  ● Streamlit
  ● VOC API
  ● Interpreter
  ● Retriever
  ● Summarizer
  ● Evaluator
  ● Critic
  ● Improver
  ● Prometheus
  ● Grafana

오른쪽: 선택한 서비스의 전용 터미널 로그
하단: [개별 시작] [개별 종료] [브라우저 열기]
```

Docker 서비스는 `docker compose up -d <service>`와 `docker compose stop <service>`로 제어하고 로그는 `docker compose logs -f <service>`로 읽는다.

Streamlit처럼 호스트 프로세스로 실행하는 서비스는 별도 `subprocess`로 관리한다.

## 14. QA 전용 GUI

별도의 `QA Control Center`를 만든다.

### 14.1 최상위 구분

```text
[AI Agent QA] [VOC QA]
```

### 14.2 AI Agent QA 탭

기준 원본은 `ai_agent_quality_portfolio/RUN/test_launcher.py`다. 기존 GUI의 하위 탭을 임의의 새 범주로 합치거나 이름을 바꾸지 않고 다음 8개를 그대로 옮긴다.

| 순서 | 기존 하위 탭명 | 기존 역할 | 현재 로컬·수업 환경 |
|---:|---|---|:---:|
| 1 | `Smoke Test` | VU 1로 기본 연결 및 HTTP 200 확인 | 모든 사용자 사용 |
| 2 | `Load Test` | 일상적인 부하 상황의 안정성 검증 | 모든 사용자 사용 |
| 3 | `Random Test` | 무작위로 변동하는 트래픽 시뮬레이션 | 모든 사용자 사용 |
| 4 | `Stress Test` | 사용자를 서서히 늘려 서버 한계점 확인 | 모든 사용자 사용 |
| 5 | `Spike Test` | 순간적인 트래픽 폭증과 복원력 검증 | 모든 사용자 사용 |
| 6 | `장애·기능 검증 시험` | k6 장애 모의, pytest 기능 검사 및 결함 보고서 확인 | 모든 사용자 사용 |
| 7 | `API 종합 성능 테스트` | API 성능 실행 및 성능 보고서 확인 | 모든 사용자 사용 |
| 8 | `API 끊김 방어 테스트` | API 단절 상황의 방어·오류 처리 검증 | 모든 사용자 사용 |

- 각 탭의 설명, VU·실행시간 입력, 시작 버튼, 탭별 콘솔을 기존과 동일하게 유지한다. 보고서 폴더 버튼은 최종 QA GUI에서 제거하고 저장 위치를 화면 설명과 문서로 안내한다.
- 로컬 통합 프로젝트에서는 원본 코드·pytest를 사용할 수 있으므로 `장애·기능 검증 시험` 탭을 포함한다.
- 신규 통합 GUI는 사용자 역할에 따라 탭을 숨기지 않고 모든 사용자에게 8개 탭을 동일하게 표시한다.
- 새 QA Control Center의 최상위에서만 `AI Agent QA` / `VOC QA`를 나누고, `AI Agent QA` 안에서는 위 원본 8개 탭 구조를 보존한다.
- 기존 구분은 보안 권한 제어가 아니라 `로컬 프로젝트 소스·pytest·app 모듈의 존재 여부`에 따른 기술적 제한이다.
- 원격 QA EXE에서 로컬 소스가 필요한 `장애·기능 검증 시험`을 누르면 클라이언트가 직접 pytest를 실행하지 않고
  통합 서버에 실행을 요청하고 진행 상태와 보고서를 조회한다.
- 고부하·장애 테스트에는 대상 주소, 예상 부하, 실행시간을 보여주는 확인 창을 두지만 역할별 권한 제한은 적용하지 않는다.
- 같은 서버를 대상으로 파괴적 성격의 테스트가 동시에 중복 실행되지 않도록 서버가 실행 잠금을 관리한다.
- 현재 로컬 QA GUI는 AI Agent QA와 VOC QA 전체 탭에 하나의 공통 실행 잠금을 적용하며, 실행 중인 탭의 중지 버튼만 활성화한다.
- 장애·기능 검증 시험의 기본 pytest는 실제 외부 AI 호출 파일과 `end_to_end` 시험을 제외한다. 실제 AI 대표 검증은 별도 승인 절차로 실행한다.

#### 14.2.1 현재 공개 정책과 AWS 전환 시 재검토

현재 개인 PC·로컬·수업 환경에서는 서버 주인과 일반 사용자를 구분하지 않는다. 동일한 QA Control
Center EXE에서 모든 테스트 탭을 볼 수 있고 고부하·장애·기능 검증 시험을 모두 실행할 수 있다.

```text
현재 로컬·수업 환경
  → 동일 QA EXE
  → 8개 테스트 탭 전체 표시
  → 역할 기반 숨김·owner token·403 권한 차단 없음
```

이 공개 정책은 AWS·클라우드에 그대로 적용하지 않는다. 외부에서 접근 가능한 서버로 배포하기 전에는
다음 항목을 필수 보안 검토 대상으로 다시 결정한다.

- 소유자 로그인 또는 재발급 가능한 owner token
- 고부하·Stress·Spike·장애 테스트의 관리자 전용 전환 여부
- 테스트별 VU·실행시간·동시 실행 제한
- HTTPS, 요청 속도 제한, 감사 로그
- 관리자 IP 허용 목록 또는 VPN 사용 여부
- 관리자 API의 서버 측 `403 Forbidden` 차단

AWS 권한 정책이 확정되기 전에는 QA 실행 API를 인터넷에 공개하지 않는다. 현재 구현에서는 나중에
인증 계층을 추가할 수 있도록 실행 API와 GUI 호출부를 분리하되 owner 기능 자체는 활성화하지 않는다.

#### 14.2.2 `장애·기능 검증 시험`의 실제 범위

기준 원본은 `ai_agent_quality_portfolio/scripts/run_validation_tests.py`이다. 이 탭은 하나의 적합·부적합만 확인하는 단일 테스트가 아니라 장애 재현, 기능 회귀 검증, 결함 보고서 생성을 한 번에 수행하는 통합 QA 파이프라인이다.

1. k6 `performance/chaos_test.js` 실행
   - 정상 HTTP 200
   - 1초 응답 지연
   - 5초 응답 지연
   - HTTP 500 오류
   - HTTP 504 타임아웃
   - 잘못된 시나리오의 HTTP 400
2. `pytest -v tests/` 실행
   - 정상 챗봇 질문 응답
   - 빈 질문 422 방어
   - Health 상태
   - Prometheus Metrics 노출
   - 실시간 리포트 생성·빈 로그 방어
   - 부정·적대적 입력 안전 처리
   - AI Agent 품질 파이프라인과 리포트 생성
3. 결과 산출물 생성
   - `_OUTPUT/reports/defects/chaos/defect_report.md`
   - 시간별 Markdown 이력본
   - `final_defect_report.docx`
4. 기존 Jira 결함 자동 등록 코드는 존재하지만 현재 호출은 주석 처리되어 비활성화 상태다.

신규 `_Total` 통합 프로젝트에서 Jira 자동 등록은 보류한다.

- `장애·기능 검증 시험`은 결함 Markdown·Word 보고서 생성까지만 자동 수행한다.
- Jira 이슈 생성 API를 호출하지 않는다.
- Jira 계정·프로젝트·API token 설정을 통합 프로젝트의 필수 환경변수에 포함하지 않는다.
- GUI에 Jira 자동 등록 버튼·옵션·자격 증명 입력란을 추가하지 않는다.
- 현재 구현의 `app/jira_client.py`는 원본 보존 원칙에 따라 삭제하지 않지만 신규 통합 실행 흐름에 연결하지 않는다. 구조 개편 시 보존이 필요하면 `src/allstar/ai_agent/api/integrations/jira_client.py`로 이동한다.
- 추후 사용자가 별도로 요청할 때 Jira 연동을 독립 기능으로 재검토한다.

통합 구현 시 Codex가 `장애·기능 검증 시험`으로 실제 AI API를 호출하는 품질 테스트케이스는 상위 지침대로 대표 2개만 사용하도록 고정한다. 현재 `test_quality_pipeline.py`의 `SAMPLE_SIZE=2`는 유지하고, 다른 자동 검증이 숨은 대량 API 호출을 추가하지 않는지 확인한다. 사용자가 GUI·대시보드에서 직접 실행하는 테스트케이스 시험은 이 제한과 분리해 전체 케이스를 사용한다.

### 14.3 VOC QA 탭

기존 `voc_upgrade/RUN/run_gui.py`의 테스트 기능을 가져온다.

- 전체 비AI 검사(pytest)
- 단위 테스트(Unit Test, LLM Judge 단위 검사 포함)
- 에이전트 교차 테스트 A
- 에이전트 교차 테스트 B
- 에이전트 교차 테스트 C
- 에이전트 교차 테스트 D
- 실행 중지
- 실행 터미널

GUI 탭은 한국어 기능명을 첫째 줄에, 괄호 안 영문명 또는 A~D 구분을 둘째 줄에 표시한다. 선택·비선택 탭은 같은 크기를 유지한다. 별도의 보고서 폴더 버튼은 두지 않고 보고서 저장 위치를 화면 설명과 문서로 안내한다.

서버 시작·종료 기능은 Server Control Center로 이동시키고, QA GUI는 테스트 실행과 결과 확인에 집중한다.

#### 14.3.1 A~D 실험군 모델 표시

기존 `voc_upgrade` GUI는 A~D 실행 버튼 안에 다음처럼 생성·평가 **제공자**를 세 줄로 표시한다.

```text
A 교차검증
생성 OpenAI
→ 평가 Anthropic
```

기존 방식은 조합을 빠르게 구분하기에는 좋지만 실제 모델명은 보여주지 않는다. 또한 기존 GUI의
`C 동일모델 검증` 표기는 버튼 문자열만 보면 생성과 평가가 모두 OpenAI라는 사실만 확인할 수 있다.
실행 환경에서 `JUDGE_OPENAI_MODEL`을 별도로 지정하면 두 모델이 달라질 수 있으므로 제공자만 보고
`동일 모델`이라고 단정하면 안 된다. 통합 QA GUI에서는 실행 시 해석한 모델명까지 비교해
`동일 모델`과 `동일 제공자`를 구분해서 표시한다.

통합 프로젝트의 확정 모델 프로필은 생성과 평가를 분리한다. OpenAI만 역할별 모델을 나누고
Anthropic은 같은 모델을 재사용하면 A~D 비교 조건이 비대칭이 되므로 두 제공자 모두 생성용과
평가용 모델을 별도로 둔다.

| 역할 | OpenAI | Anthropic |
|---|---|---|
| 생성 파이프라인 | `gpt-5.6-luna` · reasoning `none` | `claude-sonnet-4-6` · effort `low` · thinking `disabled` |
| 독립 Judge | `gpt-5.6-terra` · reasoning `low` | `claude-sonnet-5` · effort `low` · thinking `disabled` |

이에 따른 A~D 조합은 다음과 같다. 모델명은 환경변수로 변경될 수 있으므로 GUI는 아래 문자열을
고정해서 쓰지 않고 실행 시점에 해석된 실제 설정값을 표시한다.

| 실험군 | 구분 | 생성 제공자·모델 | 평가 제공자·모델 |
|---|---|---|---|
| A | 교차 제공자 검증 | OpenAI · `gpt-5.6-luna` (`OPENAI_MODEL`) | Anthropic · `claude-sonnet-5` (`JUDGE_ANTHROPIC_MODEL`) |
| B | 교차 제공자 검증 | Anthropic · `claude-sonnet-4-6` (`A2A_MODEL_POLICY`) | OpenAI · `gpt-5.6-terra` (`JUDGE_OPENAI_MODEL`) |
| C | 동일 제공자·분리 모델 검증 | OpenAI · `gpt-5.6-luna` (`OPENAI_MODEL`) | OpenAI · `gpt-5.6-terra` (`JUDGE_OPENAI_MODEL`) |
| D | 동일 제공자·분리 모델 검증 | Anthropic · `claude-sonnet-4-6` (`A2A_MODEL_POLICY`) | Anthropic · `claude-sonnet-5` (`JUDGE_ANTHROPIC_MODEL`) |

C와 D는 생성·평가 제공자는 같지만 실제 모델은 다르다. 따라서 `동일 모델 검증`이 아니라
`동일 제공자·분리 모델 검증`으로 표시한다. 모델 환경변수를 수정해 생성과 평가 모델명이 실제로
같아진 경우에만 GUI가 동적으로 `동일 모델 검증`으로 바꿔 표시한다.

각 A~D 실행 카드 또는 버튼에는 최소한 다음 내용을 직접 표시한다.

```text
A · 교차 제공자 검증
생성  OpenAI / gpt-5.6-luna
평가  Anthropic / claude-sonnet-5
```

표시 규칙:

- `A 테스트`처럼 실험군 문자만 적지 않고 생성과 평가의 제공자·모델명을 항상 함께 표시한다.
- 버튼 폭 때문에 모델명이 잘리면 말줄임표로 숨기지 않고 버튼 높이를 늘리거나 카드 형태를 사용한다.
- 환경변수로 모델이 변경되면 GUI를 다시 시작하거나 설정을 새로고침할 때 표시값도 함께 갱신한다.
- 실행 버튼을 누른 뒤 실제 프로세스에 전달할 제공자·모델 조합을 확인 영역과 실행 터미널 첫 줄에 다시 표시한다.
- 실행 결과와 보고서에도 `experiment`, `generation_provider`, `generation_model`,
  `judge_provider`, `judge_model`을 기록해 화면에 표시한 설정과 실제 호출 모델을 대조할 수 있게 한다.
- API 실패 시 대체 모델을 사용하지 않고 N/A로 기록한다는 교차검증 규칙도 A~D 영역에 고정 안내한다.
- 제공자는 같지만 모델명이 다르면 `동일 모델`이라고 표현하지 않는다. 제공자와 모델명이 모두 같을 때만
  `동일 모델 검증`으로 표시한다.

#### 14.3.2 저지연 추론 강도 정책

기본 실행은 품질에 필요한 최소 추론만 사용하고 속도를 우선한다. 생성 파이프라인은 구조화·요약·검토
프롬프트가 이미 역할별로 제한되어 있으므로 OpenAI 추론을 끈다. 최종 Judge만 판정 안정성을 위해
`low`를 사용한다. Anthropic은 생성과 Judge 모두 `low`로 제한하고 별도 thinking은 끈다.

| 구분 | 모델 | 추론 설정 | 출력 설정 |
|---|---|---|---|
| OpenAI 생성 | `gpt-5.6-luna` | `reasoning_effort=none` | `verbosity=low` |
| OpenAI Judge | `gpt-5.6-terra` | `reasoning_effort=low` | `verbosity=low` |
| Anthropic 생성 | `claude-sonnet-4-6` | `effort=low`, `thinking=disabled` | 역할별 최대 출력 제한 |
| Anthropic Judge | `claude-sonnet-5` | `effort=low`, `thinking=disabled` | Judge JSON이 잘리지 않는 범위에서 제한 |

통합 프로젝트 환경변수는 생성과 Judge가 서로 영향을 주지 않도록 분리한다.

```text
OPENAI_MODEL=gpt-5.6-luna
OPENAI_REASONING_EFFORT=none
OPENAI_VERBOSITY=low

JUDGE_OPENAI_MODEL=gpt-5.6-terra
OPENAI_REASONING_EFFORT_JUDGE=low
OPENAI_VERBOSITY_JUDGE=low

A2A_MODEL_POLICY=claude-sonnet-4-6
ANTHROPIC_EFFORT_POLICY=low
ANTHROPIC_THINKING_POLICY=disabled

JUDGE_ANTHROPIC_MODEL=claude-sonnet-5
ANTHROPIC_EFFORT_JUDGE=low
ANTHROPIC_THINKING_JUDGE=disabled
```

운영 규칙:

- 일반 챗봇과 A~D 기본 실행에서 `medium`, `high`, `xhigh`, `max`를 자동 선택하지 않는다.
- 입력이 어렵다는 이유로 실행 중 추론 강도를 자동 상향하지 않는다. 비교 조건을 고정해 재현성을 유지한다.
- Judge JSON 파싱 실패를 해결할 때는 먼저 출력 토큰 한도와 프롬프트 형식을 조정하고 추론 강도는 마지막에 검토한다.
- 사용자가 별도 고품질 실험을 요청한 경우에만 별도 실험군으로 추론 강도를 올리며 기본 설정은 변경하지 않는다.
- QA GUI의 A~D 카드와 실행 터미널에 모델명뿐 아니라 `none`·`low`·`thinking disabled`도 표시한다.
- Codex가 실제 API 속도를 검증할 때는 대표 케이스 2개만 사용하고, 모델·추론 설정·호출 횟수를 실행 전에 확인한다.

### 14.4 RUN 폴더 즉시 실행 런처

Server Control Center와 QA Control Center 모두 `RUN/`에 더블클릭용 `.bat` 파일을 함께 제공한다.

- `start_servers.bat` → `tools/server_control/main.py` 즉시 실행
- `start_qa.bat` → `tools/qa_control/main.py` 즉시 실행
- 각 `.bat`는 통합 프로젝트의 `.venv/Scripts/pythonw.exe`를 우선 사용하고, 없으면 시스템 `pyw` 또는 `pythonw`를 탐색한다.
- 실행 기준 경로는 `%~dp0`로 고정해 바로가기를 다른 위치로 옮겨도 작업 폴더가 틀어지지 않게 한다.
- 런처는 GUI를 독립 프로세스로 시작한 뒤 즉시 종료하여 별도 CMD 창이 계속 남지 않게 한다.
- `.bat`를 더블클릭하는 순간 Windows CMD 창이 짧게 깜빡일 수 있다. 이 깜빡임까지 없애기 위해 동일 GUI의 `start_*_hidden.vbs`를 함께 제공한다.
- 콘솔을 표시하지 않는 대신 시작 오류·예외는 GUI 메시지와 `_OUTPUT/logs/services/launcher/`에 자동 저장한다.

## 15. voc_upgrade 사용 시 선행 정리 대상

구현 전 분석에서 문서상 단일 패스와 실제 RPC 호출 흐름 사이에 차이가 확인됐다.

현재 RPC 서비스는 다음 에이전트를 내부에서 다시 호출한다.

- Interpreter → Retriever
- Retriever → Summarizer
- Summarizer → Evaluator
- Evaluator → Critic

동시에 중앙 오케스트레이터와 `Summarizer.run_pipeline()`도 여러 단계를 다시 호출한다.

통합 프로젝트에서는 호출 책임을 한 곳으로 정리해야 한다.

권장 원칙:

- 각 gRPC 서비스는 자신의 작업만 수행하고 결과를 반환한다.
- 전체 순서는 중앙 오케스트레이터 한 곳에서만 제어한다.
- 에이전트 간 숨은 연쇄 호출을 제거한다.
- 한 질문에서 각 생성·평가 단계가 몇 번 호출됐는지 테스트한다.

이 정리는 다음 효과를 목표로 한다.

- API 호출 중복 방지
- 처리시간 단축
- 비용 추적 정확도 향상
- 단계별 오류 위치 명확화
- 진정한 A~D 비교 조건 고정

## 16. 구현 단계

### 1단계: 통합 프로젝트 골격

- `_Total`을 통합 프로젝트로 확정
- 기존 포트폴리오 코드 복사 및 실행 확인
- VOC 업그레이드 코드 이관
- 의존성 및 환경변수 통합
- 기존 AI Agent 회귀검사

### 2단계: VOC 파이프라인 정리

- 중앙 오케스트레이터 단일 호출 구조 확정
- 6개 gRPC 에이전트 단일 책임화
- 호출 횟수와 단계별 시간 테스트
- 관련 데이터 없음 처리 고정

### 3단계: VOC HTTP API

- `/chat`, `/health`, `/agents/health`
- 대화 저장
- 백그라운드 실시간 Judge
- 실시간 리포트 생성
- Prometheus 메트릭

### 4단계: Streamlit 통합

- VOC 챗봇
- 실시간 로그 및 품질 화면
- 실시간 리포트
- A~D 테스트 결과 조회
- 교차검증 결과 조회
- VOC Grafana 임베드

### 5단계: Docker 및 모니터링

- VOC 서비스 Dockerfile
- Compose 서비스 7개 추가
- Prometheus VOC target
- Grafana VOC 대시보드
- 보고서 볼륨

### 6단계: 서버 GUI

- 전체·개별 서버 제어
- 상태 표시
- 서비스별 로그 터미널
- 브라우저 바로가기

### 7단계: QA GUI

- AI Agent QA와 VOC QA 분리
- 기존 테스트 기능 통합
- A~D 실행
- 실행 취소 및 보고서 바로가기

### 8단계: 전체 검증

- 기존 AI Agent 기능 회귀검사
- VOC 범위 외 질문 차단
- 실시간 대화 및 채점 로그 연결
- 리포트 3계열 분리 검증
- A~D 부분 결과 종합 비교
- Prometheus/Grafana 지표 확인
- Docker 전체 시작·종료
- GUI 전체·개별 제어

## 17. 완료 판단 기준

### 17.1 기존 기능 보존

- AI Agent 챗봇 정상 응답
- 기존 배치·실시간 보고서 정상 생성
- AI Agent 대화·실시간 채점·테스트케이스 실행 로그가 계열별로 자동 저장됨
- AI Agent 실시간 리포트와 테스트케이스 리포트가 서로 다른 원본 로그로 생성됨
- 기존 Prometheus/Grafana 대시보드 정상
- 기존 k6 테스트 실행 가능

### 17.2 VOC 챗봇

- VOC 질문은 검색·요약·개선안을 반환
- 질문 전 A~D 프로필을 선택할 수 있고 기본값은 A임
- A~D 카드에 생성 모델, 평가 모델, 추론 강도, 조합 목적이 표시됨
- 선택한 프로필은 질문 처리 중 변경되지 않으며 다음 질문부터 변경 가능함
- 챗봇 A~D 선택이 QA 테스트케이스 배치 실행과 명확히 구분됨
- 정상 VOC 질문은 6개 에이전트 전체와 최종 LLM Judge를 통과함
- 처리 중 입력과 전송 버튼이 비활성화되고 동시 질문이 차단됨
- `생각 중`과 경과 초가 계속 갱신되며 가능한 경우 현재 에이전트 단계를 표시함
- 전체 파이프라인과 채점 완료 전에는 최종 답변을 노출하지 않음
- 범위 외 질문은 고정 안내
- 검색 0건일 때 생성 LLM 호출 없음
- 질문과 응답이 실시간 저장됨
- Judge 결과가 동일 `request_id`로 연결됨
- 대화·채점·서비스 로그에 동일한 `profile_id`와 실제 모델 설정 스냅샷이 저장됨

### 17.3 리포트

- 실시간 대화 리포트가 테스트케이스 데이터 없이 생성됨
- 실시간 리포트 맨 앞에 A~D 의미와 생성·평가 모델·추론 강도 설명이 표시됨
- 질문별 결과 요약에 사용한 A~D 프로필과 실제 생성·평가 모델이 기록됨
- A~D별 질문 수, 성공률, 점수, 처리시간을 필터링·비교할 수 있음
- A~D 개별 리포트가 서로 다른 폴더에 생성됨
- 실행하지 않은 실험군 리포트를 임의 생성하지 않음
- A~D 중 2개 이상으로 종합 비교 리포트 생성 가능
- 세 리포트 계열의 데이터가 서로 섞이지 않음
- 리포트 원본 로그가 `_OUTPUT/logs/`의 정해진 계열별 폴더에 자동 생성됨
- 각 리포트에 연결된 manifest로 사용한 로그·기간·모델·실험군을 역추적할 수 있음
- 실행 중 중단되어도 이미 저장된 JSONL 로그는 유지됨

### 17.4 모니터링

- VOC 요청과 지연시간이 Prometheus에 수집됨
- 에이전트별 단계 시간이 Grafana에 표시됨
- 검색 0건, API 실패, Judge 판정 분포 확인 가능

### 17.5 GUI

- Server GUI에서 전체·개별 서비스 제어 가능
- 서비스별 로그 확인 가능
- QA GUI에서 AI Agent/VOC 테스트 구분 가능
- 현재 로컬·수업 환경에서 모든 사용자가 8개 AI Agent QA 탭과 VOC QA 기능을 사용할 수 있음
- 고부하·장애 테스트 실행 전 대상·부하·시간 확인 안내가 표시되고 중복 파괴 테스트가 차단됨
- 테스트 실행과 중지가 가능하며 보고서는 `_OUTPUT/reports/` 구조에 저장됨

## 18. 위험 요소

### 18.1 API 호출 중복

현재 `voc_upgrade`의 숨은 연쇄 호출이 통합되면 비용과 시간이 증가할 수 있다. 통합 초기 단계에서 우선 확인한다.

### 18.2 장시간 QA 작업

A~D 전체 80건은 저장된 과거 실행에서 약 48분 이상 걸렸다. GUI가 멈추지 않도록 별도 프로세스와 취소 기능이 필요하다.

Codex가 개발·통합 검증 명령으로 AI API를 실제 호출할 때는 대표 테스트케이스를 최대 2개로 제한한다. 사용자가 Codex에게 단순 실행을 승인해도 2개를 사용하며, A~D 비교 역시 각 실험군에 같은 2개를 재사용한다. Codex의 전체 세트 실행은 사용자가 `전체 테스트케이스 실행`을 명시한 경우에만 허용한다.

사용자가 GUI 또는 대시보드의 실행 버튼을 직접 누르면 이 제한을 적용하지 않고 실행 시점에 등록된 테스트케이스 전체를 사용한다. 실행 전에는 전체 케이스 수, 실제 AI 평가 대상 수, 프로필과 예상 호출 범위를 확인창에 표시한다. 외부 AI API를 호출하지 않는 오프라인 단위 테스트는 2개 제한의 대상이 아니다.

### 18.3 실시간 Judge 비용

모든 VOC 대화를 독립 Judge로 평가하면 사용자 질문 한 번에 파이프라인 호출과 Judge 호출이 함께 발생한다. 채점 비활성화 옵션 또는 샘플링은 추후 운영 정책으로 검토할 수 있다.

### 18.4 로그 동시 쓰기

Streamlit, FastAPI, QA 프로세스가 같은 파일을 동시에 쓸 수 있다. JSONL append 잠금 또는 단일 writer 구조가 필요하다.

### 18.5 Windows와 Docker 경로 차이

호스트는 Windows 경로, 컨테이너는 Linux 경로를 사용한다. CSV와 보고서 경로는 환경변수와 `pathlib` 기준으로 통일한다.

### 18.6 localhost와 강의실 서버 전환

대시보드 코드에 IP를 직접 넣지 않는다. 다음 환경변수로 분리한다.

```text
PORTFOLIO_API_BASE_URL=http://localhost:8000
VOC_API_BASE_URL=http://localhost:8100
GRAFANA_BASE_URL=http://localhost:3000
PROMETHEUS_BASE_URL=http://localhost:9090
```

## 19. 구현 전 최종 확정 결정

### 결정 1. 통합 작업 위치

- 결정 완료: `D:\_Study_Project\_Total`에 새 통합 프로젝트를 생성한다.
- 기존 `ai_agent_quality_portfolio`, `VOC`, `voc_upgrade` 저장소는 원본 참고용으로 보존하고 직접 확장하지 않는다.

### 결정 2. 실시간 VOC Judge 모델

- 결정 완료: 실시간 VOC 챗봇에서 A~D 모델 프로필을 선택할 수 있으며 기본값은 A로 한다.
- A는 OpenAI `gpt-5.6-luna`가 생성하고 Anthropic `claude-sonnet-5`가 독립 평가한다.
- Anthropic 생성 파이프라인은 `claude-sonnet-4-6`, 독립 Judge는 `claude-sonnet-5`로 분리한다.
- OpenAI 생성 파이프라인은 `gpt-5.6-luna`, 독립 Judge는 `gpt-5.6-terra`로 분리한다.
- 챗봇 A~D와 QA 테스트케이스 A~D는 같은 중앙 모델 프로필 정의를 사용하지만 실행과 로그·리포트 계열은 분리한다.
- 선택한 프로필의 제공자 호출이 실패해도 다른 모델로 몰래 대체하지 않는다. Judge 실패 시 답변은 표시하고 점수는 N/A로 남긴다.
- 모델별 실제 속도는 아직 같은 조건으로 측정하지 않았으므로 Codex 구현 검증에서는 대표 케이스 2개만 사용해
  처리시간과 점수 안정성을 비교한다. 측정 결과가 나오기 전에는 특정 모델이 더 빠르다고 구현 완료 문서에 단정하지 않는다.

### 결정 3. 멀티턴 대화

- 결정 완료: 초기 버전은 단발 질문만 지원한다.
- 각 질문은 독립적으로 처리하며 이전 질문과 답변 문맥을 다음 요청에 전달하지 않는다.
- 화면에서 이전 대화 기록을 조회할 수는 있지만 모델이 이를 기억해 후속 답변에 사용하지 않는다.
- 멀티턴은 초기 구현 범위에서 제외하고 추후 별도 기능으로 검토한다.

### 결정 4. Docker 중심 실행 범위

- 결정 완료: API, VOC 에이전트, Prometheus, Grafana는 Docker로 실행하고 Streamlit은 Windows 호스트에서 실행한다.
- Server Control Center가 Docker 서비스와 Streamlit 호스트 프로세스를 함께 시작·종료한다.
- Streamlit 서비스 행에 `접속` 버튼을 제공해 브라우저에서 `http://localhost:8501`을 연다.

### 결정 5. Server GUI의 로그 표현

- 결정 완료: 초기 화면은 서비스 목록 + 선택 서비스 전용 로그 영역으로 구현한다.
- 실제 구현 화면을 사용해 본 뒤 오류 요약, 다중 로그 보기, 배치 변경 필요성을 다시 검토한다.

### 결정 6. QA 테스트 권한

- 결정 완료: 현재 로컬·수업 환경에서는 고부하·장애·기능 검증 시험을 포함한 모든 QA 기능을 모든 사용자에게 제공한다.
- 역할별 탭 숨김, owner token, 관리자 전용 실행 제한은 초기 구현에서 사용하지 않는다.
- AWS·클라우드 배포 전에는 외부 공개 위험을 기준으로 테스트 권한과 인증 정책을 반드시 다시 검토한다.

## 20. 준비 단계 결론

요구사항은 하나의 통합 프로젝트로 구현 가능한 범위다.

핵심 설계 방향은 다음과 같다.

1. 기존 세 저장소는 보존하고 `_Total`에서 통합한다.
2. `voc_upgrade`를 기준으로 사용하되 gRPC 호출 책임을 중앙 오케스트레이터로 정리한다.
3. VOC용 FastAPI 게이트웨이를 `localhost:8100`에 추가한다.
4. 기존 Streamlit 대시보드에서 `AI Agent 챗봇`과 `VOC 챗봇` 두 개를 명확히 구분한다.
5. 실시간 챗봇, A~D 테스트케이스, 교차검증 종합 리포트를 분리한다.
6. 기존 Prometheus/Grafana/Docker 구조를 확장한다.
7. Server Control Center와 QA Control Center를 별도 GUI로 만든다.

구현 전 사용자 결정은 완료됐다. 위 확정안을 기준으로 1단계부터 진행한다.

> 2026-07-16 구현 시작: 초기 통합 골격과 실행 가능한 1차 기능은
> `INTEGRATED_PROJECT_IMPLEMENTATION.md`에 구현 완료·부분 구현·미검증 상태를 구분해 기록한다.
