# AllStar 문서 안내

> 갱신일: 2026-07-17

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
   - TC-01·TC-02 단일 실행, A~D 정식 보고서, 로그 기반 표·그래프와 종합 비교 기준
8. `AI_AGENT_LIVE_REPORT_AUTOMATION.md`
   - 매 채팅 백그라운드 채점, 누적 로그, 최신 보고서·표·PNG 그래프 자동 갱신 기준
9. `INTEGRATED_REPORT_DASHBOARD_REQUIREMENTS.md`
   - 기존 포트폴리오 보고서 4개 보존과 VOC 보고서 2개 추가를 포함한 통합 보고서 6개 탭 요구사항

## 현재 상태

- `src/allstar/`, `tools/`, `ops/`, `tests/`, `_OUTPUT/` 구조 전환 완료
- Python import와 실행 진입점을 `allstar.*` 기준으로 전환 완료
- Docker Compose, Server·QA GUI, Streamlit 실행 경로 전환 완료
- Python 문법 검사와 비AI 자동 테스트 완료
- 승인된 A 프로필 대표 2건의 생성 파이프라인 실행 완료
- Anthropic 인증 오류로 독립 평가는 재검증 필요
- AI Agent 실시간 채팅의 채점 완료 후 최신 보고서 자동 갱신과 데이터 기반 PNG 그래프 적용 완료

구현과 문서가 다르면 `PROJECT_DIRECTORY_STRUCTURE.md`와 실제 코드를 우선 함께 수정한다.
