# 3개 프로젝트 통합 분석 보고서

- 작성일: 2026-07-16
- 분석 대상:
  - `D:\_Study_Project\ai_agent_quality_portfolio`
  - `D:\_Study_Project\VOC`
  - `D:\_Study_Project\voc_upgrade`
- 분석 방식: 코드, 문서, 테스트 구성 및 저장된 실행 결과에 대한 읽기 전용 정적 분석
- 주의: 이 분석 과정에서는 테스트 실행, 외부 LLM 호출 및 프로젝트 코드 수정이 이루어지지 않았다.

> 후속 구조 결정: 이 문서의 폴더명은 원본 세 프로젝트와 통합 전후를 분석한 시점의 이름이다. `_Total`의 현재 구조와 새 명명 규칙은 `PROJECT_DIRECTORY_STRUCTURE.md`를 기준으로 하며, 2026-07-16에 실제 코드 이전까지 완료했다.

## 1. 전체 결론

세 프로젝트는 서로 완전히 독립된 세 종류가 아니라 두 계열로 나뉜다.

- `ai_agent_quality_portfolio`: AI 서비스의 품질관리, 관측, 장애 검증 및 운영 포트폴리오
- `VOC`: 보험 VOC 분석을 수행하는 6개 멀티에이전트 시스템의 원형
- `voc_upgrade`: `VOC`를 기반으로 속도 측정, 모델 교차검증, 보고서 생성을 강화한 후속판

새 프로젝트의 기반 코드 관점에서는 `voc_upgrade`가 가장 최신이다. `VOC`는 이전 구조와 변경 이유를 비교하는 기준선이며, `ai_agent_quality_portfolio`는 VOC 계열에 없는 웹 서비스, 대시보드, 모니터링 및 운영 QA 기능을 제공하는 별도 참고 프로젝트다.

## 2. 전체 비교

| 구분 | ai_agent_quality_portfolio | VOC | voc_upgrade |
|---|---|---|---|
| 핵심 목적 | 챗봇 품질관리와 운영 관측 | VOC 분석 및 정책 개선 | VOC의 실험·속도·검증 강화 |
| 사용자 접점 | FastAPI, Streamlit | 외부 MCP 채팅 도구 | 외부 MCP 채팅 도구 |
| 핵심 구조 | API 챗봇과 규칙 챗봇 비교 | 6개 gRPC 에이전트 | 6개 gRPC 에이전트 |
| 데이터 | 코드 내 교육과정 지식 | 보험 VOC CSV 50건 | VOC와 동일한 CSV 50건 |
| LLM | OpenAI | OpenAI + Anthropic | OpenAI + Anthropic 선택 조합 |
| 품질평가 | 5항목·25점 AI Judge | 9항목·100점 LLM Judge | 동일 기준 + A~D 교차검증 |
| 모니터링 | Prometheus/Grafana | 실행 로그 및 보고서 | 단계별 시간 및 실험별 보고서 |
| 테스트 함수 | 8개 | 49개 | 59개 |
| Python 파일 | 29개 | 36개 | 41개 |
| 대략적인 Python 코드 규모 | 4,492줄 | 6,823줄 | 8,195줄 |
| 문서 파일 | 21개 | 25개 | 47개 |
| Git 커밋 수 | 1개 | 1개 | 2개 |

코드 규모에는 생성된 Protocol Buffers 파일과 GUI 코드가 포함되어 있다.

## 3. ai_agent_quality_portfolio 분석

### 3.1 목적

이 프로젝트의 중심은 챗봇 자체보다 AI 챗봇의 답변을 어떻게 비교 평가하고, 장애를 구분하고, 운영 상태를 관측할 것인가에 있다.

### 3.2 주요 처리 흐름

```text
사용자 질문
  → FastAPI /chat
  → OpenAI 기반 답변 + 규칙 기반 답변
  → 사용자에게 우선 응답
  → 백그라운드 AI Judge 비교 채점
  → JSONL·CSV·Markdown 보고서
  → Prometheus 지표
  → Grafana 및 Streamlit 대시보드
```

### 3.3 핵심 구성

- `app/main.py`: FastAPI 서버와 전체 요청 흐름
- `app/service_agent.py`: OpenAI 기반 교육과정 안내 챗봇
- `app/rule_based_agent.py`: 키워드 기반 비교용 챗봇
- `app/judge_agent.py`: 5개 평가 항목 AI Judge
- `ai_quality/quality_pipeline.py`: 배치 비교평가 파이프라인
- `ai_quality/live_report_generator.py`: 실시간 대화 로그 보고서
- `dashboard/streamlit_app.py`: 채팅, 배치 결과, 실시간 로그 대시보드
- `monitoring/`: Prometheus와 Grafana 설정
- `performance/`: k6 성능 및 장애 시나리오
- `RUN/`: 로컬 실행용 GUI와 클라이언트

### 3.4 품질평가 방식

API형과 규칙형 답변을 동일한 기준으로 비교한다.

- 정확성
- 근거성
- 유용성
- 안전성
- 이해성

각 항목은 0~5점이며 총점은 25점이다.

- 20점 이상: PASS
- 15~19점: REVIEW
- 14점 이하: FAIL
- API 호출 실패: 품질 실패와 구분해 N/A

### 3.5 운영 및 장애 처리

- 실제 사용자 응답과 AI Judge 채점을 분리한다.
- AI Judge는 FastAPI `BackgroundTasks`로 실행한다.
- 질문과 채점 로그는 UUID `request_id`로 연결한다.
- OpenAI 호출은 최대 3회 재시도한다.
- 동시 API 호출은 세마포어로 제한한다.
- `/fault-lab`과 `/chat_mock`으로 장애 및 성능 테스트를 분리한다.
- Prometheus는 수치 지표를, JSONL은 대화 원문을 저장한다.

### 3.6 저장된 결과

배치 최종 보고서 기준:

- 테스트 케이스 5건
- API형과 규칙형 총 10개 평가 행
- AI Judge 판정 PASS 10건
- 평균 23.2/25

실시간 품질 보고서 기준:

- 실제 대화 128건
- API 기반 통과율 70.3%
- 규칙 기반 통과율 50.8%
- 평균 응답 지연 약 2,565.7ms
- 최대 응답 지연 약 15,637.9ms

성능 보고서에는 실행 조건만 있고 실제 k6 측정값은 아직 입력되지 않았다.

### 3.7 현재 구현과 문서·데이터 간 불일치

- 현재 `ai_quality/test_cases.json`에는 6개 케이스가 있지만 저장된 최종 보고서는 5개만 반영한다.
- `하루 8시간`을 기대하는 테스트가 있지만 `knowledge_base.py`에는 일일 교육시간 정보가 없다.
- `1588-5858` 연락처를 기대하는 테스트가 있지만 실제 지식베이스에는 연락처가 없다.
- 규칙 검증이 FAIL인데 AI Judge가 PASS로 판정하는 사례가 있다.
- README에는 Jira 연동이 없다고 적혀 있지만 실제 코드에는 Jira 연동이 존재한다.
- 결함 발생 시 불러오는 `quality.reports.defects.chatbot.defect_logger` 파일이 현재 저장소에 없다.
- 질문에 `퇴근` 또는 `강사`가 포함되면 장애를 발생시키는 테스트 규칙이 실제 `/chat` 경로에 포함되어 있다.
- Python 의존성 버전이 고정되어 있지 않다.
- Docker의 Prometheus와 Grafana 이미지가 `latest` 태그를 사용한다.

### 3.8 핵심 자산

- API 답변과 규칙 답변 비교평가
- 배포 전 배치 평가와 배포 후 실시간 평가 분리
- 로그, 지표, 대시보드 연결
- 장애 주입과 N/A 처리
- FastAPI, Streamlit, Prometheus, Grafana 통합 구성

## 4. VOC 분석

### 4.1 목적

보험 고객 불만 50건을 분석해 관련 VOC를 검색하고, 요약 및 정책 개선안을 생성하는 멀티에이전트 시스템이다.

### 4.2 에이전트 구성

1. Interpreter: 자연어 질문을 작업 유형과 검색 조건으로 변환
2. Retriever: CSV에서 관련 VOC 검색
3. Summarizer: 요약 후보 3개 생성
4. Evaluator: 요약 후보를 평가해 하나를 선택
5. Critic: 누락, 환각 및 품질 문제 검토
6. Improver: 정책 개선안 생성

각 에이전트는 독립 gRPC 서버로 실행된다.

| 에이전트 | 기본 포트 |
|---|---:|
| Interpreter | 6001 |
| Retriever | 6002 |
| Summarizer | 6003 |
| Evaluator | 6004 |
| Critic | 6005 |
| Improver | 6006 |

### 4.3 사용자 인터페이스

현재 자체 웹 챗봇은 없다. `main.py`가 MCP stdio 서버로 실행되며 VS Code, Cursor, Claude Desktop 같은 외부 채팅 프로그램이 사용자 대화를 담당한다.

노출되는 MCP 도구:

- `analyze_voc_nl_v2`: 자연어 질문 전체 분석
- `analyze_voc`: 필터와 작업을 직접 지정해 분석
- `health_check`: CSV 접근 상태 확인
- `summarize_voc`: VOC 요약만 생성
- `policy_from_summary`: 요약으로부터 정책 개선안 생성

### 4.4 데이터와 검색 방식

- 데이터는 `voc.csv`의 보험 고객 불만 50건이다.
- 저장 인코딩은 현재 Windows 기본 인코딩 계열이다.
- 검색은 임베딩이나 벡터 DB가 아닌 키워드 기반이다.
- 불용어 제거, 조사 제거, 제한적 동의어 처리를 사용한다.
- 구체 검색어가 여러 개일 때 최소 2~3개 일치를 요구한다.
- 1차 검색 결과가 없을 때만 동의어 검색을 사용한다.
- 필터 검색 결과는 최대 10건으로 제한한다.

### 4.5 LLM 역할

- OpenAI: 질문 해석, 요약, 후보 평가, Critic
- Anthropic: 정책 개선안
- Anthropic 호출 실패 시 OpenAI 대체 호출 가능
- 재시도 가능한 오류와 즉시 중단할 오류를 구분한다.

### 4.6 QA 구성

최초 분석 당시 테스트케이스는 총 20개였다. 2026-07-17에 연속된 두 사례마다 대표 한 건을 남기는 방식으로 현재 실행본을 10개로 축소했으며, 원본 20개는 `src/allstar/voc/evaluation/archive/test_cases_20_2026-07-17.json`에 보존한다.

- 정상 평가: TC-01~TC-16
- 현재 데이터 없음 정상 처리: TC-09 1건
- 현재 장애 검증 전용: TC-10 1건
- 축소 전 데이터 없음 TC-17~TC-18과 장애 TC-19~TC-20은 아카이브에서 확인 가능

LLM Judge는 다음 9개 항목을 총 100점으로 평가한다.

- Interpreter 해석 정확성: 15점
- Retriever 검색 관련성: 15점
- Summarizer 사실성·요약성: 15점
- Evaluator 평가 타당성: 10점
- Critic 위험 탐지력: 10점
- Improver 실행 가능성: 15점
- Agent 연계 품질: 10점
- 장애 대응·로그: 5점
- 성능: 5점

### 4.7 저장된 품질 결과

- 정상 평가: 16건
- 데이터 없음 예외 PASS: 2건
- API 실패 N/A: 0건
- 평균 점수: 65.8점
- 최종 판정: 배포 보류

낮은 점수는 주로 다음 유형에서 발생했다.

- 정보가 부족한 모호한 질문
- 서로 다른 두 문제를 함께 다루는 복합 질문
- 검색 근거가 충분하지 않은 질문
- Summarizer가 검색된 두 주제 중 하나를 누락한 경우
- Evaluator와 Critic이 앞 단계의 누락을 발견하지 못한 경우

일부 저장된 실행 결과는 한 건당 약 110~127초가 걸렸다.

### 4.8 시스템 범위

- 자체 웹 API 없음
- 자체 채팅 UI 없음
- 멀티턴 대화 기억 없음
- 사용자 인증 없음
- 데이터베이스 없음
- gRPC TLS 없음
- 로컬 프로세스 6개 실행을 전제로 함
- Tkinter GUI를 통해 서버 및 테스트 실행 가능

## 5. voc_upgrade 분석

### 5.1 VOC와의 관계

`voc_upgrade`는 `VOC`의 대체 프로젝트가 아니라 기존 파일을 유지하면서 기능을 확장한 후속판이다.

비교 결과:

- 기존 핵심 파일 삭제 없음
- 핵심 에이전트 6개 변경
- LLM 래퍼와 재시도 계층 변경
- 교차검증과 보고서 생성 파일 추가

두 저장소의 `voc.csv`와 Protocol Buffers 정의는 동일하다.

### 5.2 주요 추가 기능

- 생성 모델을 OpenAI 또는 Anthropic으로 선택하는 공통 팩토리
- OpenAI `reasoning_effort`, `verbosity`, 출력 토큰 제한
- Anthropic `effort`, `thinking` 제어
- 재시도 횟수 환경변수화
- 대체 모델 사용 여부 환경변수화
- 단계별 수행시간 기록
- Critic 이후 요약 재생성 제거
- Improver 이후 Critic 역호출 및 정책 재생성 제거
- A~D 모델 교차검증
- Word 및 PowerPoint 보고서 생성
- 모호한 `서비스가 별로예요` 질문의 최소 검색 앵커 처리

### 5.3 문서상 단일 패스

문서와 주 실행 함수가 표현하는 흐름은 다음과 같다.

```text
Interpreter
  → Retriever
  → Summarizer
  → Evaluator
  → Critic
  → Improver
  → 독립 LLM Judge
```

- Critic은 문제를 기록하지만 Summarizer를 다시 호출하지 않는다.
- Improver는 정책을 한 번만 생성한다.
- Judge는 최초 생성 결과를 평가한다.

### 5.4 실제 gRPC 호출 구조에서 확인된 차이

실제 서비스 구현에는 다음 연쇄 호출이 여전히 남아 있다.

- Interpreter RPC가 Retriever RPC를 호출
- Retriever RPC가 Summarizer RPC를 호출
- Summarizer RPC가 Evaluator RPC를 호출
- Evaluator RPC가 Critic RPC를 호출

동시에 중앙 실행부는 Interpreter 응답을 받은 뒤 Summarizer 전체 파이프라인을 다시 호출한다. Summarizer 전체 파이프라인 안에서도 Retriever, Evaluator, Critic을 명시적으로 호출한다.

따라서 현재 구현은 재생성 반복은 제거했지만 전체 요청 기준으로는 완전한 1회 호출 구조가 아니다. `test_main_pipeline_uses_single_pass_without_regeneration` 테스트는 주로 `Summarizer.run_pipeline()` 함수 내부를 검사하므로 RPC 서비스 연쇄 호출 전체의 중복 여부까지 검증하지 않는다.

이 차이는 저장된 성능 수치와 API 호출 비용을 해석할 때 중요하다.

### 5.5 A~D 교차검증

| 실험 | 생성 모델 | 평가 모델 | 목적 |
|---|---|---|---|
| A | OpenAI | Anthropic | 서로 다른 모델을 이용한 기본 교차검증 |
| B | Anthropic | OpenAI | 생성·평가 역할 변경 검증 |
| C | OpenAI | OpenAI | OpenAI 동일 계열 비교 |
| D | Anthropic | Anthropic | Anthropic 동일 계열 비교 |

교차검증 실행은 다음 조건을 고정한다.

- 재시도 1회
- 대체 모델 비활성화
- 실패 시 0점이 아닌 N/A
- 실험별 별도 보고서 폴더

### 5.6 저장된 교차검증 결과

| 실험 | 정상 채점 | 예외 PASS | N/A | 평균점수 | 점수 중앙값 | 중앙 수행시간 |
|---|---:|---:|---:|---:|---:|---:|
| A | 16 | 2 | 0 | 75.1 | 79.0 | 25.73초 |
| B | 16 | 2 | 0 | 68.9 | 74.5 | 57.25초 |
| C | 16 | 2 | 0 | 73.1 | 79.5 | 20.75초 |
| D | 16 | 2 | 0 | 70.7 | 74.0 | 62.73초 |

해당 1회 실험에서는 A의 평균 품질점수가 가장 높고 C의 중앙 수행시간이 가장 짧았다. 단일 실행 결과이므로 특정 모델 조합의 절대적 우위를 뜻하지 않는다.

### 5.7 30초 목표 실험 해석

저장된 3회 비교 결과의 전체 중앙값은 30.26초다. 다만 해당 실험에서는 Anthropic 크레딧 부족으로 OpenAI 대체 경로가 사용되었다. 따라서 이 결과를 Anthropic 저추론 설정 자체의 성능으로 해석할 수 없다.

### 5.8 자체 챗봇 상태

`_docs/VOC_전용_챗봇_분리_검토.md`에는 독립 챗봇 구현 가능성이 분석돼 있지만 실제 웹 또는 CLI 챗봇은 아직 구현되지 않았다.

현재 `run_with_question()`은 다음 한계가 있다.

- 질문 단위의 단발 실행
- 이전 대화 문맥을 기억하지 않음
- 검색 결과가 없을 때 사용자용 문구를 별도 UI가 처리해야 함
- MCP 또는 별도 호출 코드가 필요함

## 6. 프로젝트 간 기능 분류

### 6.1 ai_agent_quality_portfolio가 가진 기능

- FastAPI 웹 API
- Streamlit UI
- 실시간 대화 로그
- 배치 및 실시간 품질평가 분리
- Prometheus/Grafana
- 장애 주입
- k6 성능 테스트
- Docker Compose
- API형과 규칙형 비교

### 6.2 VOC가 가진 기능

- 보험 VOC 데이터
- 6개 에이전트 역할 정의
- MCP 인터페이스
- gRPC 통신
- 키워드 기반 검색
- 다중 요약 후보와 평가
- Critic과 정책 개선
- 100점 QA 루브릭
- 데이터 없음과 장애 케이스 구분

### 6.3 voc_upgrade가 추가한 기능

- OpenAI/Anthropic 생성 모델 교환
- 모델 교차검증
- 단계별 시간 측정
- 재시도 및 대체 정책 제어
- 실험별 N/A 처리
- Word/PPT 산출물
- 속도 비교 문서
- 단일 패스 지향 구조

## 7. 새 프로젝트 설계를 위한 현재 기준 정보

이 절은 구현안을 확정하는 내용이 아니라 세 프로젝트에서 확인된 자산을 분류한 것이다.

### 7.1 최신 VOC 도메인 기준

- 도메인 데이터와 에이전트 역할은 `voc_upgrade` 기준이 가장 최신이다.
- `VOC`는 변경 전 구조와 성능·품질 문제를 비교하는 기준선이다.

### 7.2 서비스 및 운영 기준

- 웹 API, 채팅 UI, 로그, 모니터링, 장애 테스트는 `ai_agent_quality_portfolio`에 구현돼 있다.
- VOC 계열에는 자체 사용자용 채팅 화면과 운영 모니터링이 없다.

### 7.3 품질검증 기준

- 단순 챗봇 답변 평가: `ai_agent_quality_portfolio`의 5항목·25점 구조
- 멀티에이전트 단계별 평가: VOC 계열의 9항목·100점 구조
- 모델 조합 비교: `voc_upgrade`의 A~D 교차검증 구조

### 7.4 현재 공통적으로 없는 영역

- 실제 사용자 계정과 권한 관리
- 운영 데이터베이스
- 멀티턴 대화 상태 저장
- 배포용 HTTPS와 인증된 외부 API
- 중앙 집중식 비용 추적
- 에이전트별 호출 횟수와 토큰 사용량 집계
- VOC 데이터 등록·수정 관리 화면

## 8. 분석 시점의 상태

- 세 저장소 모두 Git 작업 상태가 깨끗했다.
- `.env` 파일은 Git 추적에서 제외돼 있다.
- API 키 값은 분석 문서에 기록하지 않았다.
- 저장된 보고서 수치는 과거 실행 결과이며 현재 API, 모델 또는 코드 상태를 다시 실행해 검증한 값이 아니다.
- 이후 기능 또는 구조가 바뀌면 각 프로젝트 문서 폴더의 관련 Markdown 문서를 함께 갱신해야 한다.
