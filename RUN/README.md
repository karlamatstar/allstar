# RUN 실행 안내

`RUN/`에는 사용자가 더블클릭하는 실행 파일만 둔다. 실제 GUI 코드는 `tools/server_control/`과 `tools/qa_control/`에 있다.

## 서버 관리 (Server Control Center)

- 기본 실행: `start_servers.bat`
- CMD 창 숨김 실행: `start_servers_hidden.vbs`
- 컨테이너 실행 도구(Docker) 서비스와 Windows 호스트 통합 화면(Streamlit)의 전체·개별 시작 및 종료
- 포트 기반 상태 표시, 서비스별 실행 기록(Log), 서버 기능 명세(Swagger)·통합 화면(Streamlit)·상태 수집(Prometheus)·운영 화면(Grafana) 접속
- 우상단 `X` 종료 시 Streamlit과 현재 프로젝트의 Docker 서비스를 먼저 종료
- `RUN` 런처 사용 중 GUI가 강제 종료되면 독립 종료 감시기가 남은 서비스를 정리

시작 오류와 Streamlit 출력은 `_OUTPUT/logs/services/`에서 확인한다.
강제 종료 감시의 범위와 한계는 `_DOCS/SERVER_CONTROL_LIFECYCLE.md`를 따른다.

## 품질검사 관리 (QA Control Center)

- 기본 실행: `start_qa.bat`
- CMD 창 숨김 실행: `start_qa_hidden.vbs`
- AI 상담 품질검사(AI Agent QA)와 고객 의견 분석 품질검사(VOC QA)를 분리해 제공
- 고객 의견 분석(VOC) A~D별 답변 생성 모델·독립 품질 평가 모델(Judge)·추론 강도 표시
- 실제 외부 AI 연결(API) 시험은 대표 사례 `TC-01`, `TC-02`만 실행하며 시작 전에 호출 범위를 확인

고부하·장애 시험도 현재는 모든 사용자가 실행할 수 있다. AWS 등 외부 서버에 배포할 때 권한 분리를 다시 검토한다.
