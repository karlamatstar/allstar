# VOC 테스트케이스 Grafana 지표 연동

> 작성일: 2026-07-17
> 상태: 구현·Docker 실데이터 검증 완료

## 1. 목적

VOC A~D 테스트케이스 실행 결과는 현재 `_OUTPUT/logs/voc/testcase/`에 실행별 로그로 누적되고, `_OUTPUT/reports/voc/testcase/a~d/`의 정식 보고서로 최신 결과가 갱신된다. 기존 `VOC QA·A~D 비교` Grafana 화면은 이름과 달리 VOC 챗봇 API 지표인 `voc_chat_*`, `voc_judge_total`만 조회하므로 테스트케이스를 실행해도 값이 표시되지 않는다.

이 기능은 정식 테스트케이스 보고서를 Prometheus 수치 지표로 변환하여 다음을 만족하게 한다.

- 이미 저장된 A~D 최신 보고서를 서버 시작 후 자동으로 수집한다.
- 이후 실행 중 보고서가 갱신되면 다음 Prometheus 수집 주기에 자동 반영한다.
- Grafana에서 프로필별 평균 점수, 판정 분포, 처리시간, 테스트케이스별 결과와 평가 항목 달성률을 비교한다.
- 질문·답변·채점 근거 같은 긴 원문은 지표 라벨에 넣지 않고 기존 로그와 보고서에만 보존한다.
- Prometheus를 재시작해도 수집한 시계열이 사라지지 않게 Docker 영구 볼륨을 사용한다.

## 2. 데이터 흐름

```text
VOC A~D 테스트케이스 실행
  -> 실행별 JSON 로그 누적
  -> 프로필별 최신 JSON·CSV·Markdown·PNG 보고서 갱신
  -> VOC API /metrics가 최신 JSON 보고서를 읽어 전용 지표 노출
  -> Prometheus가 15초마다 수집하고 영구 볼륨에 저장
  -> Grafana VOC QA·A~D 비교 화면에서 표시
```

별도 Pushgateway는 추가하지 않는다. 짧게 실행되는 테스트 프로세스가 직접 메모리 지표를 보유하면 종료와 함께 값이 사라지므로, 계속 실행되는 VOC API가 공유 `_OUTPUT` 보고서를 읽어 노출하는 방식을 사용한다. 로그와 정식 보고서가 원본이고 Prometheus는 비교·추세 표시용 수치 사본이다.

## 3. 전용 지표

| 지표 | 라벨 | 의미 |
|---|---|---|
| `voc_testcase_latest_average_score` | `profile` | 최신 정상 평가 케이스 평균 점수 |
| `voc_testcase_latest_cases_total` | `profile` | 최신 보고서에 저장된 전체 케이스 수 |
| `voc_testcase_latest_case_results` | `profile`, `result` | PASS·REVIEW·FAIL·N/A별 케이스 수 |
| `voc_testcase_latest_duration_seconds` | `profile` | 최신 보고서 케이스 전체 처리시간 합계 |
| `voc_testcase_latest_case_average_duration_seconds` | `profile` | 최신 보고서 케이스 평균 처리시간 |
| `voc_testcase_latest_case_score` | `profile`, `case_id`, `result` | 최신 테스트케이스별 점수 |
| `voc_testcase_latest_case_duration_seconds` | `profile`, `case_id` | 최신 테스트케이스별 처리시간 |
| `voc_testcase_latest_criterion_achievement_percent` | `profile`, `criterion` | 평가 항목별 평균 달성률 |
| `voc_testcase_last_report_timestamp_seconds` | `profile` | 최신 보고서가 갱신된 로컬 시각의 Unix 시간 |

판정 그룹은 다음 기준으로 단순화한다.

- `PASS`: 90점 이상 또는 데이터 없음이 정상인 `PASS (예외처리)`
- `REVIEW`: 80점 이상 90점 미만
- `FAIL`: 점수가 80점 미만인 정상 채점 결과
- `N/A`: API·파이프라인 실패 등으로 숫자 점수를 만들지 못한 결과

## 4. Grafana 화면 기준

`VOC QA·A~D 비교`는 더 이상 챗봇 요청 성공·실패 수를 테스트케이스 결과처럼 표시하지 않는다. 다음 패널을 사용한다.

1. A~D 최신 평균 점수
2. PASS·REVIEW·FAIL·N/A 분포
3. 프로필별 전체·평균 처리시간
4. 평가 항목별 평균 달성률
5. 테스트케이스별 점수
6. 테스트케이스별 처리시간
7. 마지막 보고서 갱신 시각 또는 경과시간
8. 최신 보고서에 실제 저장된 테스트케이스 수

상세 질문, 실제 7단계 출력, 채점 근거는 `리포트 모음`과 `VOC 테스트케이스` 상세 화면에서 확인한다.

## 5. 보존과 예외 처리

- `_OUTPUT`에 기존 보고서가 있으면 새 API 호출 없이 해당 결과를 즉시 지표로 변환한다.
- 특정 프로필 보고서가 없으면 해당 프로필 시계열을 만들지 않으며, 이를 FAIL로 간주하지 않는다.
- JSON 파일을 쓰는 순간의 일시적인 불완전 상태나 손상 파일은 해당 수집 주기만 건너뛰고 VOC API 자체를 실패시키지 않는다.
- Prometheus 데이터는 `prometheus_data` Docker 볼륨에 보존한다.
- 실행별 원문 로그의 누적 정책과 프로필별 최신 보고서 덮어쓰기 정책은 변경하지 않는다.
- 테스트케이스 ID는 제한된 관리 목록이므로 라벨에 허용하지만 질문, 답변, 실행 ID, 요청 ID는 라벨에 넣지 않는다.

## 6. 검증 기준

- 실제 외부 AI API를 새로 호출하지 않고 기존 보고서로 지표 변환 단위 테스트를 통과한다.
- VOC API `/metrics`에서 `voc_testcase_*` 지표가 노출된다.
- Prometheus의 `voc` 수집 대상이 `up`이고 전용 지표 쿼리가 값을 반환한다.
- Grafana 자동 프로비저닝 JSON이 전용 지표만 조회한다.
- 기존 C·D 보고서가 Grafana에 표시되고 보고서가 없는 프로필은 데이터 없음으로 유지된다.
- Prometheus 컨테이너 재시작 후에도 시계열이 유지되는지 확인한다.

## 7. 2026-07-17 구현·검증 결과

- `VocTestcaseReportCollector`가 A~D의 `llm_judge_result.json`을 읽어 문서에 정의한 9종의 `voc_testcase_*` 지표를 VOC API `/metrics`에 노출한다.
- 기존 A·B·C·D 보고서를 재실행하지 않고 수집했으며 평균 점수는 A 72.125, B 65.5, C 65.0, D 75.0으로 Prometheus에서 확인했다.
- D 최신 보고서는 중단된 실행에서 완료된 6건까지만 저장된 상태이므로 FAIL 6건·나머지 0건으로 표시된다. 이는 보고서 원본을 그대로 반영한 결과이며, 완료되지 않은 나머지 사례를 임의로 N/A 처리하지 않는다.
- Grafana UID `voc-qa-abcd` 버전 3에 9개 패널을 자동 배포했다. 브라우저에서 최신 평균 점수와 PASS·REVIEW·FAIL·N/A 분포, 점수·처리시간 시계열 범례를 확인했고, 최종 프로비저닝 API에서 버전 3·9개 패널과 저장 케이스 수 쿼리를 확인했다. 저장 케이스 수는 A 10, B 10, C 10, D 6으로 조회되어 중단된 D 최신 실행을 전체 실행으로 오해하지 않게 한다.
- Prometheus `ai-agent`, `voc` 수집 대상이 모두 `up`인 상태에서 전용 지표 4개 프로필을 조회했다.
- `total_prometheus_data` 볼륨을 만든 뒤 Prometheus를 재시작했고, 재시작 전에 존재하던 C 프로필 시계열 표본 29개가 그대로 유지되는 것을 확인했다.
- 전체 비API 회귀는 `205 passed, 1 skipped`이며 외부 AI API는 호출하지 않았다. 경고 2건은 기존 Starlette 사용 중단 예정 안내와 Tk 객체 정리 경고로 이번 기능 실패가 아니다.
- 이미 실행 중인 Grafana 컨테이너에 프로비저닝 JSON을 변경한 경우 대시보드 `version`을 올리고 Grafana를 재시작해야 즉시 반영된다. 서버 전체를 새로 시작하는 정상 실행 흐름에서는 시작 시 자동 프로비저닝된다.
