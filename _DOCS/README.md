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
   - GUI 전체 테스트케이스 실행, Codex 대표 2건 검증, A~D 정식 보고서와 로그 기반 표·그래프·종합 비교 기준
8. `AI_AGENT_LIVE_REPORT_AUTOMATION.md`
   - 매 채팅 백그라운드 채점, 누적 로그, 최신 보고서·표·PNG 그래프 자동 갱신 기준
9. `INTEGRATED_DASHBOARD_STRUCTURE_REQUIREMENTS.md`
   - 왼쪽 4개·오른쪽 2개 상위 탭, AI·VOC 챗봇, 테스트케이스와 7단계 상세를 포함한 전체 화면 기준
10. `INTEGRATED_REPORT_DASHBOARD_REQUIREMENTS.md`
   - 기존 포트폴리오 보고서 4개 보존과 VOC 보고서 2개 추가를 포함한 통합 보고서 6개 탭 요구사항
11. `INTEGRATED_GRAFANA_DASHBOARD_REQUIREMENTS.md`
   - 상위 모니터링 탭 아래 기존 AI 상담·K6 2개와 VOC 신규 2개를 바로 표시하는 총 4개 하위 탭 요구사항

## 현재 상태

- `src/allstar/`, `tools/`, `ops/`, `tests/`, `_OUTPUT/` 구조 전환 완료
- Python import와 실행 진입점을 `allstar.*` 기준으로 전환 완료
- Docker Compose, Server·QA GUI, Streamlit 실행 경로 전환 완료
- Python 문법 검사와 비AI 자동 테스트 완료
- 승인된 A 프로필 대표 2건의 생성 파이프라인 실행 완료
- Anthropic 인증 오류로 독립 평가는 재검증 필요
- AI Agent 실시간 채팅의 채점 완료 후 최신 보고서 자동 갱신과 데이터 기반 PNG 그래프 적용 완료
- AI Agent 챗봇의 로컬 시간·높이 제한 메신저 화면·작성 중 스피너·완료 후 자동 갱신 적용 완료
- VOC 현재 테스트케이스 확인·수정과 수정·삭제 전 실행본 전체 이력 보관 적용 완료
- 서버 관리 상단 4개 버튼과 Docker 유지·포함 종료 분리, 최신 이미지 자동 빌드 적용 완료
- AI 에이전트 기존 테스트케이스 확인·수정과 수정·삭제 전 이력 보관 적용 완료
- Grafana iframe 내부 스크롤을 제거하고 JSON 길이에 맞춘 전체 높이 적용 완료
- 보고서 Markdown 이미지 원위치 표시와 Docker Noto CJK 한글 PNG 적용 완료
- 통합 Grafana 4개 하위 탭과 VOC Grafana JSON 2개 구현 완료, 실제 Docker 프로비저닝·실데이터 확인 필요
- 통합 대시보드의 상위 탭 6개, 챗봇·모니터링·리포트·테스트케이스 하위 화면 구현 및 비API 검증 완료
- VOC A~D 배치 실행의 테스트케이스별 7단계 실시간 상태와 완료 후 단계 상세 조회 구현·비API 공유 검증 완료

구현과 문서가 다르면 `PROJECT_DIRECTORY_STRUCTURE.md`와 실제 코드를 우선 함께 수정한다.
