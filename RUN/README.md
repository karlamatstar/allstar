# RUN 실행 안내

`RUN/`에는 사용자가 더블클릭하는 실행 파일만 둔다. 실제 GUI 코드는 `tools/server_control/`과 `tools/qa_control/`에 있다.

## Server Control Center

- 기본 실행: `start_servers.bat`
- CMD 창 숨김 실행: `start_servers_hidden.vbs`
- Docker 서비스와 Windows 호스트 Streamlit의 전체·개별 시작 및 종료
- 포트 기반 상태 표시, 서비스별 로그, Swagger·Streamlit·Prometheus·Grafana 접속

시작 오류와 Streamlit 출력은 `_OUTPUT/logs/services/`에서 확인한다.

## QA Control Center

- 기본 실행: `start_qa.bat`
- CMD 창 숨김 실행: `start_qa_hidden.vbs`
- AI Agent QA와 VOC QA를 분리해 제공
- VOC A~D별 생성 모델·평가 모델·추론 설정 표시
- 실제 AI API 시험은 대표 케이스 `TC-01`, `TC-02`만 실행하며 시작 전에 호출 범위를 확인

고부하·장애 시험도 현재는 모든 사용자가 실행할 수 있다. AWS 등 외부 서버에 배포할 때 권한 분리를 다시 검토한다.
