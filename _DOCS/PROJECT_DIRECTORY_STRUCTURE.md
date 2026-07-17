# AllStar 프로젝트 디렉터리 구조 개편 기준서

> 작성일: 2026-07-16
> 대상: `D:\_Study_Project\_Total`
> 상태: **구조 전환과 코드·Docker·GUI·테스트 경로 적용 완료**
> 개편 전 기준 커밋: `80022b0`

## 1. 문서 목적

현재 `_Total`은 기존 AI Agent 프로젝트와 VOC 프로젝트를 먼저 통합하는 과정에서 원본 프로젝트의 폴더명을 상당 부분 유지했다. 기능 통합에는 유리했지만 다음 문제가 남았다.

- `app/`만 보고는 어떤 서비스인지 알기 어렵다.
- `quality/`와 `ai_quality/`가 비슷한 이름이지만 각각 리포트와 실행 코드를 뜻한다.
- 동일한 VOC 기능이 `voc/`와 `voc_api/`로 나뉘어 있다.
- `dashboard/`, `RUN/`, `scripts/`에 사용자 화면과 실행 도구가 섞여 있다.
- 실행 산출물이 `logs/`와 `quality/reports/`로 떨어져 있어 한 번에 찾기 어렵다.
- 여러 파일이 프로젝트 루트를 각자 계산하고 출력 경로를 직접 조립한다.

이 문서는 2026-07-16에 적용한 폴더 구조와 이름의 현재 기준을 정의한다. 이후 구조를 바꿀 때도 이 문서와 실제 구현을 함께 갱신한다.

## 2. 구조 설계 원칙

1. 실제 프로그램 코드는 `src/allstar/` 아래에 둔다.
2. AI Agent와 VOC는 각각 하나의 도메인 폴더로 묶는다.
3. `quality`라는 포괄적인 이름 대신 자동 채점·검증 기능에는 `evaluation`을 사용한다.
4. `app`, `utils`, `misc`처럼 대상을 알 수 없는 최상위 이름을 사용하지 않는다.
5. 사용자가 직접 실행하는 파일과 내부 Python GUI 코드를 분리한다.
6. 운영 설정은 `ops/`, 개발·실행 보조 도구는 `tools/`에 둔다.
7. 실행 중 만들어지는 모든 파일은 `_OUTPUT/` 아래에만 저장한다.
8. 원본 로그는 `_OUTPUT/logs/`, 사람이 확인하는 결과는 `_OUTPUT/reports/`에 저장한다.
9. `_DOCS/`에는 기준·설계·사용법 문서만 두고 실행 리포트 사본을 만들지 않는다.
10. 경로 상수는 `src/allstar/shared/paths.py`에서 중앙 관리한다.

## 3. 최종 목표 구조

```text
_Total/
├─ src/
│  └─ allstar/
│     ├─ __init__.py
│     ├─ ai_agent/
│     │  ├─ api/                      AI Agent FastAPI와 서비스 코드
│     │  └─ evaluation/               규칙 검증, Judge, 배치·실시간 평가
│     ├─ voc/
│     │  ├─ api/                      VOC HTTP API
│     │  ├─ agents/                   6개 gRPC 에이전트
│     │  ├─ llm/                      OpenAI·Anthropic 연결
│     │  ├─ runtime/                  실행 설정, 재시도, gRPC 런타임
│     │  ├─ mcp/                      MCP 도구
│     │  ├─ evaluation/               LLM Judge, A~D, 교차검증, 보고서 생성
│     │  ├─ protocol/                 voc.proto와 생성된 gRPC 코드
│     │  └─ data/                     voc.csv 등 실행 데이터
│     ├─ ui/
│     │  └─ dashboard/                통합 Streamlit 화면
│     └─ shared/
│        ├─ paths.py                  프로젝트·로그·리포트 중앙 경로
│        ├─ model_profiles.py         A~D 모델 프로필 단일 원본
│        └─ single_instance.py        Windows 컨트롤러 중복 실행 공통 잠금
├─ tools/
│  ├─ server_control/                 Server Control Center Python 코드
│  ├─ qa_control/                     QA Control Center Python 코드
│  └─ scripts/                        검증·방화벽·리포트 실행 보조 도구
├─ ops/
│  ├─ docker/                         서비스별 Dockerfile
│  ├─ monitoring/                     Prometheus·Grafana 설정
│  └─ performance/                    k6 성능·부하 시나리오
├─ tests/
│  ├─ ai_agent/
│  ├─ voc/
│  └─ integration/
├─ RUN/                               사용자가 더블클릭하는 파일만 보관
│  ├─ start_servers.bat
│  ├─ start_servers_hidden.vbs
│  ├─ start_qa.bat
│  └─ start_qa_hidden.vbs
├─ _OUTPUT/
│  ├─ logs/
│  │  ├─ ai_agent/
│  │  │  ├─ live/
│  │  │  │  ├─ conversations/
│  │  │  │  └─ judgments/
│  │  │  └─ testcase/
│  │  ├─ voc/
│  │  │  ├─ live/
│  │  │  │  ├─ conversations/
│  │  │  │  └─ judgments/
│  │  │  ├─ testcase/
│  │  │  └─ cross_validation/
│  │  ├─ qa/
│  │  │  ├─ runs/
│  │  │  └─ k6/
│  │  └─ services/
│  └─ reports/
│     ├─ qa/
│     │  └─ latest/
│     ├─ ai_agent/
│     │  ├─ batch/
│     │  └─ live/                      최신 실시간 Markdown·CSV와 데이터 기반 PNG
│     │     └─ assets/
│     ├─ voc/
│     │  ├─ live/
│     │  ├─ testcase/                  A~D 프로필별 최신 정식 보고서·데이터·그래프
│     │  └─ cross_validation/          2개 이상 프로필의 최신 종합 비교
│     ├─ defects/
│     ├─ performance/
│     └─ manifests/
├─ _DOCS/
├─ .env
├─ .env.example
├─ .gitignore
├─ compose.yml                         표준 실행 진입점이므로 루트 유지
├─ pyproject.toml
├─ requirements.txt
└─ README.md
```

## 4. 최상위 폴더 역할

| 폴더 | 역할 | 포함하면 안 되는 것 |
|---|---|---|
| `src/` | 실제 서비스와 화면 코드 | 로그, 리포트, 실행 결과 |
| `tools/` | 서버·QA 제어 및 일회성 실행 도구 | 핵심 API 비즈니스 로직 |
| `ops/` | Docker, 모니터링, 성능시험 설정 | 서비스 소스 코드 |
| `tests/` | 자동 테스트 코드 | 실제 운영 로그와 리포트 |
| `RUN/` | 더블클릭 진입용 `.bat`, `.vbs` | 장문의 Python 구현 코드 |
| `_OUTPUT/logs/` | 대화·채점·테스트·서비스 원본 기록 | 사람이 읽는 최종 보고서 |
| `_OUTPUT/reports/` | CSV·JSON·Markdown·PNG 그래프·Word·PPT 결과 | Python 실행 코드 |
| `_DOCS/` | 설계, 기준, 사용법, 구현 상태 | 자동 생성 리포트 사본 |

## 5. 현재 경로에서 목표 경로로의 변경표

| 현재 경로 | 목표 경로 | 처리 기준 |
|---|---|---|
| `app/` | `src/allstar/ai_agent/api/` | `app`이라는 일반 이름 제거 |
| `ai_quality/` | `src/allstar/ai_agent/evaluation/` | 품질평가 코드를 AI Agent 아래로 결합 |
| `voc_api/` | `src/allstar/voc/api/` | VOC HTTP API를 VOC 도메인 아래로 이동 |
| `voc/agents/` | `src/allstar/voc/agents/` | 역할이 명확하므로 이름 유지 |
| `voc/llm_wrappers/` | `src/allstar/voc/llm/` | 짧고 직접적인 이름 사용 |
| `voc/grpc_server.py` | `src/allstar/voc/runtime/grpc_runtime.py` | 프로토콜 정의와 실행 런타임 분리 |
| `voc/utils/env_loader.py` 등 실행 보조 | `src/allstar/voc/runtime/` | 환경설정·재시도·사전검사를 런타임으로 묶음 |
| `voc/utils/tools.py` | `src/allstar/voc/mcp/tools.py` | MCP 도구의 실제 역할 표시 |
| `voc/quality_diagnosis/`의 실행 코드 | `src/allstar/voc/evaluation/` | Judge·교차검증·보고서 생성 통합 |
| `voc/quality_diagnosis/test_*.py` | `tests/voc/evaluation/` | 제품 코드와 테스트 분리 |
| `voc/voc.proto`, `voc_pb2*.py` | `src/allstar/voc/protocol/` | gRPC 정의와 생성 코드 결합 |
| `voc/voc.csv` | `src/allstar/voc/data/voc.csv` | 실행 데이터 위치 명시 |
| `dashboard/` | `src/allstar/ui/dashboard/` | 통합 사용자 화면으로 분류 |
| `config/model_profiles.py` | `src/allstar/shared/model_profiles.py` | AI Agent·VOC 공통 설정으로 분류 |
| `RUN/server_control_gui.py` | `tools/server_control/main.py` | 내부 GUI 코드를 실행 파일과 분리 |
| `RUN/qa_control_gui.py` | `tools/qa_control/main.py` | 내부 GUI 코드를 실행 파일과 분리 |
| `scripts/` | `tools/scripts/` | 실행 보조 도구를 한곳에 정리 |
| `monitoring/` | `ops/monitoring/` | 운영 설정으로 분류 |
| `performance/` | `ops/performance/` | 성능시험 시나리오로 분류 |
| `Dockerfile.*` | `ops/docker/` | 서비스별 이미지 정의 결합 |
| `docker-compose.yml` | `compose.yml` | 표준 이름으로 바꾸되 루트 진입점 유지 |
| `tests/`의 혼합 테스트 | `tests/ai_agent`, `tests/voc`, `tests/integration` | 대상 서비스 기준으로 분리 |
| `logs/` | `_OUTPUT/logs/` | 모든 실행 원본을 산출물 폴더로 결합 |
| `quality/reports/` | `_OUTPUT/reports/` | 애매한 `quality` 폴더 제거 |
| `logs/report_manifests/` | `_OUTPUT/reports/manifests/` | 리포트와 연결되는 메타데이터로 분류 |

## 6. 명명 규칙

### 6.1 폴더

- Python 패키지는 소문자 `snake_case`를 사용한다.
- 서비스 영역은 `ai_agent`, `voc`처럼 실제 대상을 이름에 포함한다.
- 자동 채점·평가·리포트 생성 코드는 `evaluation`으로 통일한다.
- HTTP 진입점은 각 도메인의 `api/` 아래에 둔다.
- 모델 연결 코드는 `llm/`, 통신 정의는 `protocol/`, 실행 보조는 `runtime/`으로 구분한다.
- `app`, `utils`, `misc`, `temp`, `quality`를 새로운 최상위 폴더명으로 사용하지 않는다.

### 6.2 Python 파일

- API 시작 파일은 `api/main.py`로 통일한다.
- GUI 시작 파일은 각 도구 폴더의 `main.py`로 통일한다.
- 역할이 다른 기능을 하나의 `utils.py`에 계속 추가하지 않는다.
- 공통 경로는 `shared/paths.py`, 모델 프로필은 `shared/model_profiles.py`를 단일 원본으로 사용한다.

### 6.3 실행 결과

- 로그 파일명에는 날짜 또는 실행 ID를 포함한다.
- 최신 리포트와 이력 리포트를 분리한다.
- A~D 테스트 결과는 프로필과 케이스 ID를 경로에 포함한다.
- 소스 폴더에는 실행 결과 파일을 생성하지 않는다.

## 7. 중앙 경로 관리

개편 후 각 모듈이 `Path(__file__).parent.parent` 방식으로 프로젝트 루트를 개별 계산하지 않는다. `src/allstar/shared/paths.py`에 다음 기준을 둔다.

```text
PROJECT_ROOT
OUTPUT_ROOT
LOG_ROOT
REPORT_ROOT
AI_AGENT_LOG_ROOT
AI_AGENT_REPORT_ROOT
VOC_LOG_ROOT
VOC_REPORT_ROOT
SERVICE_LOG_ROOT
MANIFEST_ROOT
```

Docker와 Windows 호스트에서 경로가 달라질 수 있으므로 환경변수로 루트 경로를 덮어쓸 수 있게 하되, 기본값은 `_Total/_OUTPUT`으로 한다.

## 8. 적용한 이전 작업 순서

### 1단계: 새 골격과 공통 경로

- `src/allstar/`, `tools/`, `ops/`, `_OUTPUT/` 골격 생성
- `pyproject.toml`을 `src` 패키지 구조에 맞게 수정
- `shared/paths.py`와 경로 단위 테스트 작성

### 2단계: 산출물 경로 이전

- `logs/`를 `_OUTPUT/logs/`로 변경
- `quality/reports/`를 `_OUTPUT/reports/`로 변경
- Docker 볼륨, GUI 로그 화면, 리포트 링크 수정
- 기존 실행 파일은 삭제하지 않고 새 위치로 안전하게 옮긴 뒤 내용 검증

### 3단계: AI Agent 코드 이전

- `app/`을 `src/allstar/ai_agent/api/`로 이동
- `ai_quality/`를 `src/allstar/ai_agent/evaluation/`로 이동
- import, API 시작 명령, 테스트 경로 수정

### 4단계: VOC 코드 이전

- `voc_api/`와 `voc/`를 `src/allstar/voc/` 아래 역할별로 결합
- gRPC proto import와 생성 코드 경로 수정
- A~D 실행 스크립트와 리포트 경로 수정

### 5단계: 화면·도구·운영 설정 이전

- Streamlit을 `src/allstar/ui/dashboard/`로 이동
- Server·QA GUI Python 코드를 `tools/`로 이동
- `RUN/`에는 `.bat`, `.vbs`, 짧은 안내문만 유지
- Dockerfile, 모니터링, 성능시험 파일을 `ops/`로 이동

### 6단계: 테스트와 문서 정리

- 테스트를 `ai_agent`, `voc`, `integration`으로 분류
- 전체 import 및 옛 경로 문자열 검색
- README, 실행 문서, Docker 문서 갱신
- 모든 검증이 끝난 뒤에만 빈 옛 폴더 제거

## 9. 검증 기준

- `app/`, `ai_quality/`, `voc_api/`, 최상위 `voc/`, `quality/`, `logs/`가 남아 있지 않아야 한다.
- Python import가 모두 `allstar.*` 기준으로 동작해야 한다.
- Portfolio API와 VOC API의 Health가 모두 `200`이어야 한다.
- VOC 에이전트 6개가 정상 기동해야 한다.
- Streamlit 화면과 Server·QA Control Center가 새 경로에서 실행되어야 한다.
- `_OUTPUT/logs/`와 `_OUTPUT/reports/` 밖에 실행 산출물이 생성되지 않아야 한다.
- 기존 A~D 프로필, 보고서 형식, 로그 필드가 구조 개편 때문에 달라지지 않아야 한다.
- GUI·대시보드의 사용자 직접 실행은 등록된 전체 테스트케이스를 사용한다. 명령행 검증 범위는 실행 목적과 예상 외부 호출 범위를 확인한 뒤 명시적으로 선택하며 2건으로 고정하지 않는다.

## 10. 구현 상태 체크리스트

- [x] 목표 구조 확정
- [x] 현재 경로와 목표 경로 매핑 작성
- [x] 명명 규칙 작성
- [x] 이전 순서와 완료 조건 작성
- [x] `src/allstar/` 실제 생성 및 코드 이전
- [x] `_OUTPUT/` 실제 생성 및 경로 이전
- [x] `tools/`, `ops/`, `tests/` 실제 재배치
- [x] Docker·GUI·Streamlit 실행 경로 수정
- [x] 비AI 회귀 테스트
- [x] 구조 전환 이후 AI 전체 6건과 VOC A~D 전체 10건 실제 API 실행 확인

## 11. 이번 구조 전환의 검증 범위

폴더 이동, `allstar.*` import 전환, Docker Compose·GUI·Streamlit 경로 수정, Python 문법 검사와 비AI 회귀 테스트를 수행했다. 구조 전환 당시에는 실제 AI API를 호출하지 않았으나, 이후 AI 에이전트 등록 전체 6건과 VOC A·B·C·D 각각 등록 전체 10건 실행을 완료했다. 현재 실행 전에는 화면에 표시되는 전체 사례 수, 모델과 외부 호출 범위를 확인한다.
