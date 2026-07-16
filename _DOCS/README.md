# AllStar 문서 안내

> 갱신일: 2026-07-16

`_DOCS/`에는 설계, 구현 상태, 준비 기록을 저장한다. 실행 로그와 자동 생성 리포트는 `_OUTPUT/`에 저장한다.

## 읽는 순서

1. `PROJECT_DIRECTORY_STRUCTURE.md`
   - 현재 적용된 `src/allstar` 구조와 이름 규칙
   - 이전 경로와 새 경로의 대응 관계
2. `INTEGRATED_PROJECT_IMPLEMENTATION.md`
   - 통합 기능의 현재 구현 상태와 실행 방식
   - 테스트와 Docker 검증 기록
3. `VOC_PORTFOLIO_INTEGRATION_PREPARATION.md`
   - AI Agent·VOC 통합 요구사항
   - A~D 모델, 로그, 리포트, GUI, QA 기준
4. `PROJECT_ANALYSIS_SUMMARY.md`
   - 원본 프로젝트 분석과 통합 판단 근거

## 현재 상태

- `src/allstar/`, `tools/`, `ops/`, `tests/`, `_OUTPUT/` 구조 전환 완료
- Python import와 실행 진입점을 `allstar.*` 기준으로 전환 완료
- Docker Compose, Server·QA GUI, Streamlit 실행 경로 전환 완료
- Python 문법 검사와 비AI 자동 테스트 완료
- 실제 AI API 대표 2건 시험은 비용이 발생하므로 이번 구조 전환에서는 실행하지 않음

구현과 문서가 다르면 `PROJECT_DIRECTORY_STRUCTURE.md`와 실제 코드를 우선 함께 수정한다.
