# RUN 실행 안내

`RUN/`에는 사용자가 더블클릭하는 실행 파일만 둔다. 실제 GUI 코드는 `tools/server_control/`과 `tools/qa_control/`에 있다.

## 서버 관리 (Server Control Center)

- 기본 실행: `start_servers.bat`
- CMD 창 숨김 실행: `start_servers_hidden.vbs`
- 컨테이너 실행 도구(Docker) 서비스와 Windows 호스트 통합 화면(Streamlit)의 전체·개별 시작 및 종료
- 포트 기반 상태 표시, 서비스별 실행 기록(Log), 서버 기능 명세(Swagger)·통합 화면(Streamlit)·상태 수집(Prometheus)·운영 화면(Grafana) 접속
- 우상단 `X` 종료 시 Streamlit과 현재 프로젝트의 Docker 서비스를 먼저 종료
- `RUN` 런처 사용 중 GUI가 강제 종료되면 독립 종료 감시기가 남은 서비스를 정리
- 상태 확인을 백그라운드에서 동시에 처리하여 화면 멈춤과 새로고침 중복을 방지
- 실행 서비스 목록에서 Docker Desktop 상태 확인 및 개별 시작·종료
- `전체 시작` 시 Docker Desktop이 꺼져 있으면 먼저 실행하고 준비 완료 후 프로젝트 서버 시작
- PID 기록이 없는 이전 Streamlit도 8501 포트 점유 여부로 찾아 종료
- 개별 시작·종료 아래에 기능 명세 2개, 통합 대시보드, Prometheus, Grafana 바로가기를 고정 배치
- 바로가기의 🟢/⚪ 아이콘으로 접속 가능 여부를 표시하고 중지 상태에서는 서버 시작 안내 제공
- Docker가 꺼진 상태에서 Docker 서비스 개별 시작 시 한국어 경고를 실행 기록 화면에 표시
- 서버 관리 GUI는 기본 `1440×900`, 최소 `1200×820` 크기로 실행하고 화면 중앙에 배치

시작 오류와 Streamlit 출력은 `_OUTPUT/logs/services/`에서 확인한다.
강제 종료 감시의 범위와 한계는 `_DOCS/SERVER_CONTROL_LIFECYCLE.md`를 따른다.

## 품질검사 관리 (QA Control Center)

- 기본 실행: `start_qa.bat`
- CMD 창 숨김 실행: `start_qa_hidden.vbs`
- AI 상담 품질검사(AI Agent QA)와 고객 의견 분석 품질검사(VOC QA)를 분리해 제공
- 고객 의견 분석(VOC) A~D별 답변 생성 모델·독립 품질 평가 모델(Judge)·추론 강도 표시
- 실제 외부 AI 연결(API) 시험은 대표 사례 `TC-01`, `TC-02`만 실행하며 시작 전에 호출 범위를 확인

고부하·장애 시험도 현재는 모든 사용자가 실행할 수 있다. AWS 등 외부 서버에 배포할 때 권한 분리를 다시 검토한다.
