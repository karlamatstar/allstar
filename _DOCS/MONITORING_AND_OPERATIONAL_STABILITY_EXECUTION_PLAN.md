# 모니터링 상세 보강과 운영 안정성 검증 실행 계획

> 작성일: 2026-07-18
> 기준 프로젝트: `D:\_Study_Project\_Total`
> 사용자 승인: 대표 테스트케이스 2건의 실제 OpenAI·Anthropic API 사용 허용
> 시작 상태: Docker Desktop만 실행, 프로젝트 컨테이너·Streamlit·관리 GUI는 종료
> 현재 상태: 1차 모니터링 구현·검증·푸시 완료, 2차 운영 안정성·대표 2건 실제 API 검증 완료

## 1. 목적

이번 작업은 다음 두 묶음을 순서대로 완료한다.

1. 모니터링 상세 보강
   - VOC 7단계 에이전트별 처리시간·오류율
   - 검색 결과 0건과 VOC API 실패 원인별 분포
   - 통합 Streamlit의 핵심 서버 운영 상태 요약
2. 운영 안정성 검증
   - 장시간 실행
   - Docker 재시작
   - 프로젝트 Docker 네트워크 변동
   - 다중 사용자 동시 사용

기능 구현, 시험 조건, 실행 결과를 구분해서 기록한다. 계획만 확정된 항목은 검증 완료로 표시하지 않는다.

## 2. 사용량 부족 가능성과 중단·재개 기준

2026-07-18 작업 시작 시점에 사용자가 확인한 GPT Pro 잔여 표시는 약 30%다. 이 비율을 정확한 토큰 수나 남은 작업시간으로 환산할 수는 없으므로 전체 작업이 한 번에 끝난다고 보장하지 않는다.

작업 중 사용량 부족이 발생해도 안전하게 이어갈 수 있도록 다음 순서를 지킨다.

1. 1차 모니터링 상세 구현을 코드·시험·문서까지 완료한다.
2. 1차 결과를 별도 커밋으로 `origin/main`에 푸시한다.
3. 2차 운영 안정성 검증을 시작하기 전에 기준 상태와 실행 조건을 파일로 저장한다.
4. 각 안정성 시험 결과는 실행 중 JSONL에 누적하고 완료 단계는 상태 파일에 기록한다.
5. Docker·네트워크 시험은 제한시간 뒤 자동 복구되는 명령으로 실행한다.
6. 각 큰 검증 단계가 끝날 때 문서와 커밋을 남긴다.
7. 사용량이 소진되면 마지막 완료 상태 다음 단계부터 이어서 진행한다.

1차 푸시가 끝난 뒤의 2차 시험 중 작업이 중단되어도 이미 게시된 모니터링 구현과 문서는 영향을 받지 않는다.

## 3. 1차 모니터링 상세 보강

### 3.1 VOC 7단계 지표

대상 단계는 `Interpreter`, `Retriever`, `Summarizer`, `Evaluator`, `Critic`, `Improver`, `LLM Judge`다.

기존 `_OUTPUT/logs/voc/progress/*.json`에는 실행별 프로필, 테스트케이스, 단계 시작·종료 시각과 `done`·`failed`·`skipped` 상태가 누적된다. Prometheus는 이 파일을 읽어 다음 집계를 제공한다.

- 프로필 A~D
- 실행 종류: 실시간 챗봇·A~D 배치
- 단계별 완료·실패·건너뜀 횟수
- 단계별 평균·p95 처리시간
- 단계별 오류율

질문 원문, 답변, 오류 전문과 실행 ID는 Prometheus 라벨로 사용하지 않는다.

### 3.2 검색 결과와 실패 원인

Retriever 단계 결과를 다음 고정 분류로 집계한다.

- `found`: 검색 결과 존재
- `no_data`: 검색 결과 0건
- `error`: 검색 처리 실패

0건·실패 이유는 `no_match`, `retry_exhausted`, `empty_filter`, `timeout`, `connection`, `data_source`, `unknown`처럼 개수가 제한된 값만 사용한다.

VOC 외부 API·파이프라인 실패는 `auth`, `rate_limit`, `timeout`, `connection`, `provider_server`, `response_parse`, `unknown`으로 정규화한다. 제공자는 오류에서 확인 가능한 경우 `openai`·`anthropic`, 확인할 수 없으면 `unknown`으로 기록한다. 인프라·외부 API 장애는 품질 `FAIL`로 바꾸지 않고 기존 기준대로 `N/A`를 유지한다.

### 3.3 Grafana

`VOC 챗봇 실시간 운영` 화면에 다음 패널을 추가한다.

- 7단계 평균 처리시간
- 7단계 p95 처리시간
- 단계별 오류율
- 검색 결과 분포
- 검색 결과 0건·검색 실패 원인 분포
- 외부 API·파이프라인 실패 원인 분포

필요하면 `VOC QA·A~D 비교`에도 같은 지표를 배치 실행 기준으로 분리해 표시한다. 원본 JSON과 자동 프로비저닝 복사본은 항상 같은 내용으로 유지한다.

### 3.4 통합 Streamlit 운영 상태 요약

모니터링 화면 상단에 다음 핵심 상태를 표시한다.

- AI 에이전트 API
- VOC API
- VOC 에이전트 6개
- Prometheus
- Grafana

정상·준비 중·중단 상태, 정상 수/전체 수, 마지막 확인 시각, 새로고침을 제공한다. 기본 화면은 요약 카드로 간단히 표시하고 상세 영역에서 서비스별 응답시간과 실패 이유를 확인한다. 상태 확인은 Health·TCP 연결만 사용하며 외부 AI API를 호출하지 않는다.

## 4. 1차 완료 기준과 푸시

- 새 Prometheus 지표가 데이터가 없을 때도 의미 있는 0 또는 빈 상태를 제공한다.
- 누적 진행 기록을 통해 Docker 재시작 뒤에도 과거 집계가 복원된다.
- Grafana 원본·프로비저닝 JSON의 패널과 PromQL이 일치한다.
- Streamlit에서 핵심 서버 상태를 한눈에 확인할 수 있다.
- 외부 AI를 호출하지 않는 단위·통합·구조 시험이 통과한다.
- 관련 기준 문서와 프로젝트 체크리스트를 구현 상태에 맞게 갱신한다.
- 1차 결과만 별도 커밋해 `origin/main`에 푸시한다.

## 5. 2차 운영 안정성 검증

1차 푸시가 끝난 뒤 다음 순서로 진행한다.

1. 기준 상태 기록
   - 컨테이너, Health, CPU·메모리, 지표, 로그·보고서 수
2. 장시간 실행
   - 1차 로컬 검증은 비과금 모의 요청과 Health 확인을 30분간 10초 간격으로 관찰
   - 실제 운영 전 인증 시험에서는 같은 도구로 1~2시간까지 실행 시간을 늘릴 수 있음
3. Docker 재시작
   - 프로젝트 컨테이너 재시작 후 데이터·지표·마지막 활동 복원 확인
4. 네트워크 변동
   - 프로젝트 Docker 네트워크의 대상 컨테이너만 일시 분리하고 자동 재연결
5. 다중 사용자
   - 비과금 요청으로 1명·10명·25명 조건 확인
6. 실제 API 종단 검증
   - 대표 테스트케이스 2건만 사용
7. 결과 문서화와 단계별 커밋·푸시

호스트 전체 인터넷을 강제로 끄거나 다른 프로젝트 컨테이너를 중단하지 않는다. 네트워크·Docker 시험은 종료 시 `docker compose up -d`와 Health 확인으로 정상 상태를 복구한다.

### 5.1 재실행 가능한 검증 도구

`tools/scripts/run_operational_stability.py`는 외부 AI API를 호출하지 않고 아래 시험을 독립 실행한다.

```powershell
.\.venv\Scripts\python.exe tools\scripts\run_operational_stability.py baseline
.\.venv\Scripts\python.exe tools\scripts\run_operational_stability.py concurrency
.\.venv\Scripts\python.exe tools\scripts\run_operational_stability.py soak --duration-seconds 1800 --interval-seconds 10
.\.venv\Scripts\python.exe tools\scripts\run_operational_stability.py docker-restart
.\.venv\Scripts\python.exe tools\scripts\run_operational_stability.py network-variation
```

- `baseline`: AI API, VOC API, Prometheus, Grafana와 VOC 6개 에이전트 포트를 확인한다.
- `concurrency`: 실제 OpenAI·Anthropic 대신 `/chat_mock`을 사용해 1명·10명·25명을 단계별 독립 실행한다.
- `soak`: 서비스 10개와 비과금 모의 채팅을 지정 시간 동안 반복 확인한다.
- `docker-restart`: `_Total` Compose 컨테이너만 재시작하고 10개 서비스 복구와 Prometheus 누적 시계열 보존을 확인한다.
- `network-variation`: VOC API 컨테이너만 `total_default`에서 일시 분리해 장애 감지를 확인하고 `finally` 절차로 재연결한다.

실행별 원본 이벤트는 `_OUTPUT/logs/services/operational_stability/`에 JSONL로 누적한다. 최신 요약은 `_OUTPUT/reports/operations/operational_stability_latest.json`과 `operational_stability_latest.md`에 덮어쓴다. 이 출력은 운영 검증 자료이며 Git에는 포함하지 않는다.

## 6. 실제 API 사용 승인 범위

실제 API는 모니터링 구현 자체나 다중 사용자 부하 생성에 사용하지 않는다. 다음 종단 확인에만 사용한다.

- VOC 7단계 실제 처리와 새 지표 반영
- Docker 재시작 뒤 외부 제공자 연결 복구
- 네트워크 복구 뒤 정상 답변·Judge·보고서·지표 갱신

Codex가 실행할 때는 대표 테스트케이스 2개만 사용하며 A~D 비교에서도 같은 2개를 재사용한다. 실제 실행 직전에 테스트케이스 ID, 프로필, 제공자와 예상 호출 범위를 사용자에게 다시 알린다. 전체 테스트케이스는 사용자가 `전체 테스트케이스 실행`을 명시한 경우에만 사용한다.

## 7. 문서 갱신 대상

- `INTEGRATED_GRAFANA_DASHBOARD_REQUIREMENTS.md`
- `INTEGRATED_DASHBOARD_STRUCTURE_REQUIREMENTS.md`
- `PROJECT_PROGRESS_CHECKLIST.md`
- `REMAINING_WORK_PLAN.md`
- 본 실행 계획의 구현·검증 결과 절

## 8. 1차 구현·검증 결과

2026-07-18에 다음을 구현했다.

- 누적 진행 JSON 기반 `voc_stage_runs_total`
- 누적 진행 JSON 기반 `voc_stage_duration_seconds`
- 검색 결과·원인 지표 `voc_retrieval_results_total`
- 제공자·단계·원인별 `voc_pipeline_failures_total`
- 검색 결과 0건의 `no_match`·`retry_exhausted`·`empty_filter` 기록
- VOC 실시간 Grafana 9개에서 15개 패널로 확장
- VOC QA·A~D Grafana 9개에서 15개 패널로 확장
- Streamlit 모니터링 상단의 핵심 서버 10개 상태 요약

비과금 집중 시험 29건이 통과했다. 외부 AI 시험 2개 파일과 VOC `end_to_end`를 제외한 전체 회귀는 `274개 통과·1개 환경 제외·2개 선택 제외`다. Docker 이미지를 재생성한 뒤 AI·VOC API, VOC 6개 에이전트, Prometheus, Grafana가 정상 상태로 올라왔다. `/metrics`에서 단계 상태 시계열 168개와 단계 처리시간 시계열 56개를 확인했고 과거 D 배치의 Interpreter 실패 5건도 복원됐다. Prometheus 수집 대상 `ai-agent`와 `voc`는 모두 `up`이며 Grafana 두 화면은 각각 15개 패널로 프로비저닝됐다. 새 패널의 PromQL 전체가 Prometheus API에서 정상 처리됐다.

실제 Streamlit 화면의 `모니터링` 탭에서 정상 서비스 `10 / 10`, 중단·오류 `0`, 5초 자동 확인과 서비스별 상태 카드를 확인했다. 실제 Grafana `VOC 챗봇 실시간 운영` 화면에서도 기존 9개와 신규 6개 패널 제목이 모두 렌더링됐다. 이 브라우저 검증에서도 실제 외부 AI API는 호출하지 않았다.

Docker 빌드 최초 실행은 짧은 명령 대기 제한과 재실행이 겹쳐 같은 Compose 프로젝트 컨테이너 이름 충돌이 발생했다. `total` 프로젝트만 `docker compose down`으로 정리한 뒤 다시 시작해 정상 복구했다. 다른 프로젝트 컨테이너와 Docker 데이터 볼륨은 정리하지 않았다.

## 9. 2차 운영 안정성·실제 API 검증 결과

### 9.1 비과금 운영 안정성

검증일은 2026-07-18이며 Windows 호스트, Docker Desktop, `_Total` Compose 컨테이너 10개 조건에서 실행했다.

- 기준 상태: AI API, VOC API, Prometheus, Grafana, VOC 에이전트 6개가 모두 정상인 `10/10`
- 동시 사용자: `/chat_mock`으로 1명·10명·25명을 단계별 독립 실행했으며 각각 `1/1`, `10/10`, `25/25` 성공
- 동시 사용자 p95: 1명 `2,099.94ms`, 10명 `2,514.56ms`, 25명 `3,632.07ms`
- Compose 재시작: 컨테이너 10개가 모두 복구됐고 Prometheus 시계열 수는 재시작 전후 `1,497 → 1,497`
- 네트워크 변동: VOC API만 `total_default`에서 분리했을 때 에이전트 연결 저하를 감지했고 재연결 뒤 에이전트 6개와 Prometheus `voc` 수집 대상이 모두 복구됨
- 장시간 실행: 30분(`1,800초`), 10초 대기 간격, 130표본, 실패 0건, 모의 채팅 p95 `2,100.59ms`
- 컨테이너 합계 메모리: 관찰 중 기준 `831.66MiB`, 종료 직후 `792.21MiB`로 지속 증가 징후 없음
- 최신 전체 비과금 회귀: `281개 통과·1개 환경 제외·2개 선택 제외`

네트워크 첫 구현은 일반 `docker network connect`만 사용해 VOC API 자체는 복구됐지만 Compose 서비스 별칭 `voc-api`가 사라져 Prometheus 대상이 `down`으로 남는 문제를 발견했다. 재연결 시 `--alias voc-api`를 함께 복원하고, 복구 완료 조건에 Prometheus `voc` 대상 `up`을 추가했다. 최종 재검증에서 에이전트 6개와 Prometheus가 모두 정상으로 돌아왔다.

Grafana 재시작 로그에서는 선택 기능용 `plugins`·`alerting` 프로비저닝 폴더 부재와 사용하지 않는 추천 플러그인 갱신 권한 경고를 발견했다. 빈 폴더를 저장소에 포함하고 `GF_PLUGINS_PREINSTALL_DISABLED=true`를 적용해 Grafana만 재생성했다. 재생성 뒤 Health `ok`, 새 시작 로그의 오류 0건을 확인했다.

### 9.2 대표 2건 실제 API 종단 검증

사전 고지한 범위 그대로 프로필 A의 `TC-01`, `TC-02`만 실행했다. 생성은 OpenAI `gpt-5.6-luna`·추론 끔, 독립 평가는 Anthropic `claude-sonnet-5`·낮음을 사용했다. B·C·D와 나머지 8개 사례는 실행하지 않았다.

| 사례 | 파이프라인 | Judge | 전체 | 점수 | 판정 |
|---|---:|---:|---:|---:|---|
| TC-01 | 15.00초 | 12.71초 | 27.72초 | 81점 | 조건부 배포 가능, 개선 후 재검증 |
| TC-02 | 14.30초 | 13.10초 | 27.42초 | 68점 | 배포 보류 |

두 사례 모두 OpenAI 생성 파이프라인과 Anthropic Judge가 정상 완료됐고 API·파싱 실패는 없었다. 누적 지표에는 A 배치 검색 성공 2건과 A 배치 `LLM Judge done` 2건이 추가됐다.

실행 뒤 지정 2건 개발 검증도 A 최신 정식 보고서를 교체하는 기존 동작을 발견했다. 방금 실행 결과는 `_OUTPUT/logs/voc/testcase/a/ops_validation_20260718_0935/`의 실행 로그·초안에 그대로 보존하고, 2026-07-17의 마지막 정상 A 전체 10건 원본 로그로 최신 정식 보고서와 종합 비교를 복원했다. Prometheus에서 A 최신 정식 사례 수가 다시 `10`임을 확인했다.

후속 코드에서는 `--case-id`로 일부 사례를 지정한 실행을 `partial_validation`으로 표시하고 최신 정식 보고서·프로필 manifest·종합 비교를 갱신하지 않는다. 현재 등록된 전체 범위를 정상 완료한 실행만 `full` 정식 보고서로 승격한다.
