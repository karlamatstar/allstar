# RUN 실행 도구

## Server Control Center

`start_server_control.bat`를 더블클릭하면 Docker 서비스와 Windows 호스트 Streamlit을 한 화면에서 관리한다.

- 전체·개별 시작과 종료
- 포트 기반 상태 표시
- 선택 서비스 전용 로그
- Streamlit, Swagger, Prometheus, Grafana 접속

CMD 창의 순간적인 표시까지 숨기려면 `start_server_control_hidden.vbs`를 실행한다.

시작 오류와 Streamlit 출력은 `logs/services/`에서 확인한다.

## QA Control Center

`start_qa_control.bat`를 더블클릭하면 AI Agent QA와 VOC QA를 분리해 실행한다.

- AI Agent QA는 기존 8개 테스트 구분을 유지한다.
- VOC QA는 전체·단위 테스트와 A~D 대표 2건 실행을 제공한다.
- A~D 화면에 생성 모델, 평가 모델, 추론 설정을 표시한다.
- 실제 AI API 또는 고부하·장애 테스트는 대상과 호출 범위를 확인한 뒤 실행한다.
- `start_qa_control_hidden.vbs`는 CMD 창 표시 없이 실행한다.
