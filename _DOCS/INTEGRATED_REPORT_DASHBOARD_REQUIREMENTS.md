# 통합 결과 보고서 대시보드 요구사항

> 작성일: 2026-07-17  
> 적용 대상: `_Total` 통합 Streamlit의 `통합 결과 보고서(Report)` 영역  
> 상태: **화면 설계 확정, 실제 코드 미구현**

## 1. 목적

기존 `ai_agent_quality_portfolio` 대시보드에서 제공하던 네 가지 보고서를 `_Total` 통합 대시보드에서도 그대로 확인할 수 있게 한다. 여기에 신규 VOC 기능의 실시간 챗봇 보고서와 A~D 테스트케이스 보고서를 추가한다.

이 문서는 화면과 데이터 연결 요구사항만 정리한다. 이번 문서 작성에서는 Streamlit 코드, 보고서 생성 코드, API 및 저장 경로를 변경하지 않는다.

## 2. 목표 탭 구성

`통합 결과 보고서(Report)` 영역에는 총 6개의 보고서 탭을 둔다.

| 순서 | 보고서 탭 | 구분 | 상태 |
|---:|---|---|---|
| 1 | AI 상담 챗봇 보고서 | 기존 포트폴리오 보존 | 화면 이식 대상 |
| 2 | 장애·기능 검증 보고서 | 기존 포트폴리오 보존 | 화면 이식 대상 |
| 3 | 서버 연결 성능 보고서 | 기존 포트폴리오 보존 | 화면 이식 대상 |
| 4 | AI 상담 테스트케이스 보고서 | 기존 포트폴리오 보존 | 화면 이식 대상 |
| 5 | 고객 의견 분석(VOC) 챗봇 보고서 | 신규 추가 | 화면 추가 대상 |
| 6 | 고객 의견 분석(VOC) A~D 테스트케이스 보고서 | 신규 추가 | 화면 추가 대상 |

기존 네 보고서는 내용과 역할을 줄이거나 하나로 합치지 않는다. 신규 VOC 보고서도 기존 AI Agent 보고서의 원본 데이터와 섞지 않는다.

## 3. 기존 포트폴리오 보고서 4개

### 3.1 AI 상담 챗봇 보고서

- 실제 AI Agent 사용자 대화와 규칙 기반·API 기반 답변의 실시간 Judge 결과를 보여준다.
- 채점 완료 후 자동 갱신되는 최신 Markdown과 데이터 기반 PNG 그래프를 표시한다.
- 상단 요약 표와 그래프를 먼저 보여주고, FAIL·REVIEW·N/A 및 최근 채팅 목록의 접기·펼치기 동작을 유지한다.

```text
_OUTPUT/reports/ai_agent/live/live_report.md
_OUTPUT/reports/ai_agent/live/live_report.csv
_OUTPUT/reports/ai_agent/live/assets/*.png
```

### 3.2 장애·기능 검증 보고서

- QA 컨트롤러의 `장애·기능 검증 시험(Validation Test)` 결과를 보여준다.
- 장애 재현 결과, 기능 회귀 검사, 결함 내역과 종합 판정을 기존 보고서 형식 그대로 표시한다.
- Word 보고서는 후속 문서 재정리 자료로 유지하고 대시보드 본문은 Markdown을 우선 표시한다.

```text
_OUTPUT/reports/defects/chaos/defect_report.md
_OUTPUT/reports/defects/chaos/final_defect_report.docx
```

### 3.3 서버 연결 성능 보고서

- QA 컨트롤러의 `서버 연결 성능 종합 시험(API)` 결과를 보여준다.
- 요청 수, 성공·실패, 평균·최대·백분위 응답시간, 질문별 지연과 병목 분석을 표시한다.

```text
_OUTPUT/reports/performance/performance_report.md
ops/performance/results/raw_latency.json
```

### 3.4 AI 상담 테스트케이스 보고서

- 규칙 기반 챗봇과 API 기반 챗봇의 배치 테스트케이스 비교 결과를 보여준다.
- 모델별 판정, 품질 항목 점수, 테스트 유형별 비교와 케이스 상세를 유지한다.
- Markdown 보고서뿐 아니라 CSV를 활용한 기존 품질 현황·유형별 비교·케이스 상세 화면도 보존한다.

```text
_OUTPUT/reports/ai_agent/batch/final_quality_report.md
_OUTPUT/reports/ai_agent/batch/evaluation_result.csv
_OUTPUT/reports/ai_agent/batch/evaluation_result.json
```

## 4. 신규 VOC 보고서 2개

### 4.1 고객 의견 분석(VOC) 챗봇 보고서

- 실제 VOC 챗봇 대화와 독립 Judge 결과를 집계한 최신 보고서를 표시한다.
- A~D 의미, 실제 생성·평가 모델, 추론 강도, 프로필별 질문 수·성공률·점수·처리시간을 보여준다.
- 질문별 최종 답변과 7단계 처리 결과, N/A·실패·취소 내역을 확인할 수 있게 한다.
- A~D 프로필을 사용하더라도 실시간 보고서는 하나의 통합 보고서 계열로 유지한다.

```text
_OUTPUT/reports/voc/live/latest/voc_live_report.md
_OUTPUT/reports/voc/live/history/
```

이 탭은 최신 보고서 표시를 기본으로 한다. VOC 실시간 보고서의 자동 또는 수동 생성 방식 변경은 이번 문서 작업 범위에 포함하지 않는다.

### 4.2 고객 의견 분석(VOC) A~D 테스트케이스 보고서

최상위 보고서 탭은 하나만 추가하고, 그 안에서 A·B·C·D 개별 보고서와 종합 비교를 선택하게 한다.

권장 내부 구성:

```text
VOC A~D 테스트케이스 보고서
├─ A
├─ B
├─ C
├─ D
└─ 종합 비교
```

- A~D 선택 영역에는 해당 프로필 보고서 존재 여부와 최신 실행 상태를 표시한다.
- 실행하지 않은 프로필은 실패가 아니라 `실행 결과 없음`으로 표시한다.
- 프로필을 선택하면 TC-01·TC-02를 합친 최신 정식 Markdown과 표·PNG 그래프를 표시한다.
- 프로필 결과가 2개 이상 존재하면 `종합 비교`에서 A~D 최신 결과를 비교한다.
- 프로필 하나만 존재하면 종합 비교 영역에 최소 2개 결과가 필요하다는 안내를 표시한다.

```text
_OUTPUT/reports/voc/testcase/a/quality_score_report.md
_OUTPUT/reports/voc/testcase/b/quality_score_report.md
_OUTPUT/reports/voc/testcase/c/quality_score_report.md
_OUTPUT/reports/voc/testcase/d/quality_score_report.md
_OUTPUT/reports/voc/testcase/{a|b|c|d}/assets/*.png

_OUTPUT/reports/voc/cross_validation/교차검증_종합비교보고서.md
_OUTPUT/reports/voc/cross_validation/assets/*.png
```

## 5. 공통 화면 규칙

- 사용자는 보고서 파일 경로를 직접 입력하거나 폴더를 열지 않고 대시보드 안에서 내용을 확인한다.
- Markdown의 표, 배지, 접기·펼치기와 PNG 이미지를 그대로 표시한다.
- 긴 보고서는 상단 요약과 그래프를 먼저 보여주고 상세 목록은 아래에 둔다.
- 보고서가 없으면 빈 화면이나 오류 대신 어떤 시험 또는 대화를 먼저 진행해야 하는지 한국어로 안내한다.
- 보고서 파일이 없다는 이유로 실행하지 않은 프로필이나 API 미평가를 FAIL로 바꾸지 않는다.
- N/A는 FAIL과 분리하고, 점수 평균과 품질 그래프에는 각 보고서의 기존 집계 기준을 적용한다.
- 보고서 화면은 최신 결과를 우선 표시하며 원본 누적 로그를 직접 수정하지 않는다.
- API 키, 시스템 프롬프트, 내부 사고 과정과 비밀 설정은 보고서 화면에 표시하지 않는다.

## 6. 보고서와 QA 공통 실행 요약의 관계

`_OUTPUT/reports/qa/latest/`의 Markdown은 QA 실행 상태와 원문 로그를 연결하는 보조 요약이다. 이번 6개 탭은 해당 보조 요약을 정식 품질 보고서 대신 표시하지 않는다.

향후 별도의 `최근 QA 실행` 영역을 추가할 수 있지만, 다음 보고서는 각각 독립된 정식 결과물로 유지한다.

- AI Agent 실시간 챗봇 보고서
- 장애·기능 검증 보고서
- 서버 연결 성능 보고서
- AI Agent 배치 테스트케이스 보고서
- VOC 실시간 챗봇 보고서
- VOC A~D 개별·종합 테스트케이스 보고서

## 7. 구현 시 완료 기준

- 통합 결과 보고서 영역에 6개 탭이 모두 표시된다.
- 기존 포트폴리오 보고서 4개의 내용과 사용 흐름이 보존된다.
- VOC 챗봇 보고서와 VOC A~D 테스트케이스 보고서가 각각 독립 탭으로 표시된다.
- A~D는 최상위 탭을 여러 개 만들지 않고 하나의 탭 내부에서 선택한다.
- 종합 비교는 사용 가능한 프로필이 2개 이상일 때만 표시하거나 활성화한다.
- Markdown 표·접기·펼치기와 PNG 그래프가 대시보드에서 정상 표시된다.
- 보고서가 없는 모든 경우에 한국어 안내가 표시된다.
- 실제 보고서 생성 로직과 누적 로그는 화면 이식 전후에 동일하게 유지된다.

## 8. 이번 문서 작업에서 하지 않은 것

- `src/allstar/ui/dashboard/streamlit_app.py` 수정
- 기존 `portfolio_legacy.py` 화면 코드 이동
- 보고서 생성 또는 실제 AI API 호출
- 보고서 파일·그래프 신규 생성
- 대시보드 실행 및 화면 테스트

따라서 현재 상태는 요구사항 정리 완료이며, 통합 대시보드의 6개 탭은 아직 구현되지 않았다.
