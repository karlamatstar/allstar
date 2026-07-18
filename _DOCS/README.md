# AllStar 문서 안내

> 갱신일: 2026-07-18

`_DOCS/`에는 설계, 구현 상태, 준비 기록을 저장한다. 실행 로그와 자동 생성 리포트는 `_OUTPUT/`에 저장한다.

## 읽는 순서

1. `PROJECT_PROGRESS_CHECKLIST.md`
   - 구현·검증·문서화·실제 API·Git 반영을 분리한 전체 진행 현황
   - 다음에 해야 할 작업과 최신 검증 결과
2. `PROJECT_DIRECTORY_STRUCTURE.md`
   - 현재 적용된 `src/allstar` 구조와 이름 규칙
   - 이전 경로와 새 경로의 대응 관계
3. `INTEGRATED_PROJECT_IMPLEMENTATION.md`
   - 통합 기능의 현재 구현 상태와 실행 방식
   - 테스트와 Docker 검증 기록
4. `VOC_PORTFOLIO_INTEGRATION_PREPARATION.md`
   - AI Agent·VOC 통합 요구사항
   - A~D 모델, 로그, 리포트, GUI, QA 기준
5. `PROJECT_ANALYSIS_SUMMARY.md`
   - 원본 프로젝트 분석과 통합 판단 근거
6. `QA_REPORT_AUTOMATION.md`
   - QA 누적 로그, 최신 보고서 덮어쓰기, manifest와 실제 대표 검증 결과
7. `VOC_TESTCASE_REPORT_AUTOMATION.md`
   - 현재 등록된 전체 테스트케이스 실행, A~D 정식 보고서와 로그 기반 표·그래프·종합 비교 기준
8. `AI_AGENT_LIVE_REPORT_AUTOMATION.md`
   - 매 채팅 백그라운드 채점, 누적 로그, 최신 보고서·표·PNG 그래프 자동 갱신 기준
9. `INTEGRATED_DASHBOARD_STRUCTURE_REQUIREMENTS.md`
   - 왼쪽 4개·오른쪽 3개 상위 탭, K6 부하 시험, AI·VOC 챗봇과 테스트케이스를 포함한 전체 화면 기준
10. `INTEGRATED_REPORT_DASHBOARD_REQUIREMENTS.md`
   - 기존 포트폴리오 보고서 4개 보존과 VOC 보고서 2개 추가를 포함한 통합 보고서 6개 탭 요구사항
11. `INTEGRATED_GRAFANA_DASHBOARD_REQUIREMENTS.md`
   - 상위 모니터링 탭 아래 기존 AI 상담·K6 2개와 VOC 신규 2개를 바로 표시하는 총 4개 하위 탭 요구사항
12. `VOC_UI_FOLLOWUP_IMPROVEMENTS.md`
   - 테스트케이스 실행 상태 배지 외부 배치, 진행 중 단계 스크롤 안전 여백, VOC 선택 카드 강조와 메신저형 채팅 구현·반응형 검증 기록
13. `VOC_TESTCASE_GRAFANA_METRICS.md`
   - VOC A~D 정식 보고서를 Prometheus 전용 지표로 변환하고 Grafana에 기록·보존하는 기준
14. `AI_QUALITY_DASHBOARD_UI_IMPROVEMENTS.md`
   - AI 챗봇 메시지 배치, 실시간·배치 좌우 품질 비교와 페이지 이동, 레이더·정확한 점수표 구현 기준
15. `VOC_CHATBOT_QUALITY_AND_FAILURE_IMPROVEMENT_PLAN.md`
   - VOC 챗봇 5개 품질 하위 탭, 공통 9항목·100점 채점 전환, 2026-07-17 검색 0건 실패 분석과 후속 개선 기준
16. `AI_AGENT_KNOWLEDGE_SYNC.md`
   - 규칙 기반·API 기반 지식 불일치 원인과 전체 지식 자동 전달·누락 방지 기준
17. `CONTROL_CENTER_SINGLE_INSTANCE.md`
   - 서버·품질검사 관리 중복 실행 경고, Windows 공통 잠금과 서버 종료 감시기 예외 처리 기준
18. `AI_AGENT_TESTCASE_REPORT_CHARTS.md`
   - AI 에이전트 테스트케이스 정식 보고서의 데이터 기반 PNG 그래프와 최신·이력 보존 기준
19. `VOC_LIVE_REPORT_PRESENTATION.md`
   - VOC 챗봇 보고서의 한눈에 보는 품질 현황, A~D 그래프, 접이식 확인 목록과 최신순 채팅 목록 기준
20. `QA_CONTROL_UI.md`
   - 품질검사 관리의 시험 탭, 실행 잠금, 중지, K6와 실제 API 확인 절차
21. `QA_AI_TESTCASE_TAB_AND_K6_REPORT_POLICY.md`
   - QA 컨트롤러 AI 테스트케이스 탭 추가, 직접 부하 K6 5종과 기존 장애·성능 정식 보고서의 보존 범위
22. `SERVER_CONTROL_LIFECYCLE.md`
   - 서버 관리의 전체 시작·종료, Docker 포함 종료, Streamlit 잔류 프로세스 정리 기준
23. `REMAINING_WORK_PLAN.md`
   - 완료 기능을 제외한 실제 미완료·재검증·AWS 검토 항목의 우선순위
24. `DASHBOARD_K6_LOAD_TEST_PLAN.md`
   - K6 부하 테스트 상위 탭, 7개 시험 카드, 실행 상태·중지·터미널과 Docker K6 필수 조건
25. `AI_CHAT_FAULT_TEST_BUTTONS.md`
   - AI 챗봇 503·504·실제 서버 중단 버튼, N/A 로그·보고서와 재접속 기준
26. `CHAT_SERVER_STATUS_AND_RECONNECT.md`
   - AI·VOC 채팅 서버별 Health 감지, 입력 잠금, 중앙 중단 안내와 독립 재접속 기준
27. `MONITORING_AND_OPERATIONAL_STABILITY_EXECUTION_PLAN.md`
   - VOC 7단계 상세 지표, 핵심 서버 10개 상태 요약과 장시간·재시작·네트워크·동시 사용자 검증 순서 및 결과
28. `DOCKER_STREAMLIT_K6_RUNNER.md`
   - 로컬 Docker Streamlit, K6 전용 실행 서비스, 공유 데이터·중지·AWS 선택 기준
29. `CHAT_SERVICE_CONTROL_BRIDGE.md`
   - Docker Streamlit의 AI 실제 서버 중단과 AI·VOC 재접속을 위한 제한된 서비스 제어 기준

## 문서 상태 해석 원칙

- 현재 상태는 `PROJECT_PROGRESS_CHECKLIST.md`, 이 문서, `INTEGRATED_PROJECT_IMPLEMENTATION.md`, `REMAINING_WORK_PLAN.md` 순서로 교차 확인한다.
- 기능별 기준은 해당 기능 전용 문서가 우선이며, 여러 문서가 충돌하면 실제 코드와 최신 체크리스트를 함께 갱신한다.
- 과거 실행 수치와 실패 기록은 당시 조건을 보존하는 이력이다. 최신 전체 회귀 수치처럼 해석하지 않는다.
- `PROJECT_ANALYSIS_SUMMARY.md`는 원본 3개 프로젝트를 통합하기 전의 읽기 전용 분석 기록이며 현재 `_Total` 구현 상태를 뜻하지 않는다.
- `_OUTPUT/`은 실행 산출물이고 `_DOCS/`는 설계·구현·운영 기준이다. 실행 산출물을 Git 문서로 옮기거나 비밀값을 기록하지 않는다.

## 현재 상태

- `src/allstar/`, `tools/`, `ops/`, `tests/`, `_OUTPUT/` 구조 전환 완료
- Python import와 실행 진입점을 `allstar.*` 기준으로 전환 완료
- Docker Compose, Server·QA GUI, Docker Streamlit과 K6 전용 실행 경로 전환 완료
- 서버·품질검사 관리가 이미 실행 중이면 경고 후 두 번째 실행만 종료하는 단일 실행 잠금 적용 완료
- Python 문법 검사와 외부 AI 실행 경로를 제외한 최신 비API 회귀 `288개 통과·1개 환경 제외·2개 선택 제외`
- OpenAI·Anthropic 인증을 복구하고 AI 배치 등록 전체 6건과 VOC A~D 각각 등록 전체 10건·종합 비교 실제 검증 완료
- 이후 AI 에이전트 실시간 질문과 VOC 동일 질문 A~D에서는 OpenAI·Anthropic 호출과 독립 채점이 정상 완료됨
- AI Agent 실시간 채팅의 채점 완료 후 최신 보고서 자동 갱신과 데이터 기반 PNG 그래프 적용 완료
- AI Agent 챗봇의 로컬 시간·높이 제한 메신저 화면·작성 중 스피너·완료 후 자동 갱신 적용 완료
- VOC 현재 테스트케이스 확인·수정과 수정·삭제 전 실행본 전체 이력 보관 적용 완료
- 서버 관리 상단 4개 버튼과 Docker 유지·포함 종료 분리, 최신 이미지 자동 빌드 적용 완료
- AI 에이전트 기존 테스트케이스 확인·수정과 수정·삭제 전 이력 보관 적용 완료
- Grafana iframe 내부 스크롤을 제거하고 JSON 길이에 맞춘 전체 높이 적용 완료
- 보고서 Markdown 이미지 원위치 표시와 Docker Noto CJK 한글 PNG 적용 완료
- 통합 Grafana 4개 하위 탭, AI 실제 채팅 지표 분리, K6 Prometheus 실시간 전송, VOC 챗봇 9개·VOC QA 9개 패널과 영구 보존 검증 완료
- VOC 챗봇·QA Grafana를 각각 15개 패널로 확장하고 7단계 평균·p95·오류율, 검색 0건과 제공자·파이프라인 실패 원인 분포 적용 완료
- 통합 Streamlit 모니터링 상단의 AI·VOC·6개 에이전트·Prometheus·Grafana 총 10개 상태와 5초 자동 확인 적용 완료
- Grafana의 브라우저·운영체제 설정 기반 자동 라이트·다크 테마와 열린 iframe 실시간 전환 적용
- 보고서 모음 6개 탭 명칭·순서 정리와 AI 에이전트 테스트케이스 PNG 그래프 3개 생성 완료
- VOC 챗봇 보고서의 상단 A~D 모델·평가기준 상시 노출, 품질 요약, PNG 그래프 3개와 기본 닫힘 상세 목록 구현 완료
- 대시보드 오른쪽 테스트 영역의 `K6 부하 테스트`와 7개 실행 카드·환경 상태·중지·터미널 구현 완료
- K6 카드의 4열·2열·1열 반응형 배치, 행별 동일 높이, `[-] [숫자] [+]` 입력, 가상 인원 1~999명·시간 10~600초 보정과 길게 누르기 자동 증감 구현 완료
- K6 실시간 터미널의 최신 출력 자동 스크롤과 중지·실패 시 마지막 정상 보고서 보호 구현 완료
- 통합 대시보드의 상위 탭 7개, 챗봇·모니터링·리포트·K6·테스트케이스 화면 구현 및 비API 검증 완료
- AI·VOC 테스트케이스 관리/실행 탭 분리와 AI 배치 분석 3개 탭 보존 완료
- 상위·하위 탭 버튼형 구분, 브라우저 설정 기반 라이트·다크 자동 테마와 1024px·600px·390px 반응형 검증 완료
- VOC A~D 배치 실행의 테스트케이스별 7단계 실시간 상태와 완료 후 단계 상세 조회 구현·비API 공유 검증 완료
- VOC 테스트케이스 실행 외부 상태 배지·진행 단계 스크롤 안전 여백, 확인 기반 선택 카드와 520px 메신저형 VOC 채팅 구현·브라우저 검증 완료
- AI 챗봇 필수 확인·채팅·입력창 연결, 사용자/AI 좌우 정렬, 입력 중 상태와 실시간·배치 품질 좌우 비교·페이지 이동·정확한 점수표 구현 완료
- VOC 챗봇의 5개 품질 하위 탭·공통 9항목 100점 전환·검색 0건 재시도와 `no_data` 분리·손상 입력 차단 구현 및 실제 A~D 검증 완료
- AI 에이전트 챗봇의 `퇴근`·`강사` 특수어 강제 장애 규칙과 공개 강제 연결 끊김 요청 필드, QA 컨트롤러의 전용 연결 끊김 방어 시험 제거 완료
- 루트 README를 대시보드 상위 7개 탭과 하위 기능 중심으로 전면 정리하고 AI 등록 6건·VOC 등록 10건의 현재 전체 실행 기준 반영 완료
- 제품 문서의 대표 2건 고정 정책을 제거하고 화면은 현재 등록 전체 실행, 명령행은 명시적 사례 선택 방식으로 통일
- 컨트롤러 단일 실행, 보고서 그래프·VOC 최신 보고서, Grafana 전체화면 후속 개선을 커밋 `452cf22`로 `origin/main`에 반영 완료
- 밀린 문서 상태·이력·남은 작업 정합성 정리를 커밋 `486ec52`로 `origin/main`에 반영 완료
- 모니터링 상세 지표·Grafana 패널·Streamlit 서버 상태 요약을 커밋 `5d5db86`으로 `origin/main`에 반영 완료
- 운영 안정성 자동 검증, 30분·재시작·네트워크·동시 사용자 결과, 부분 VOC 검증의 정식 보고서 보호를 커밋 `8e6e4cc`로 `origin/main`에 반영 완료

QA 컨트롤러 AI 테스트케이스 탭, 직접 부하 K6 보고서 범위 분리, AI·VOC 테스트케이스 정상 완료 보고서 보호를 구현·비API 검증했다. 2026-07-18에 30분 장시간·Compose 재시작·네트워크 변동·1명/10명/25명 동시 사용자와 A 대표 2건 실제 API 종단 검증을 완료했다. 지정 사례 개발 검증은 실행별 초안만 유지하고 전체 범위 정식 보고서를 바꾸지 않도록 보완했다. Streamlit 컨테이너와 K6 전용 실행 서비스도 로컬 Docker 기준으로 구현·검증했으며 AWS는 선택 사항이다. 정확한 항목은 `PROJECT_PROGRESS_CHECKLIST.md`를 따른다.

구현과 문서가 다르면 `PROJECT_DIRECTORY_STRUCTURE.md`와 실제 코드를 우선 함께 수정한다.
