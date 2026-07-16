# 서버 관리 프로그램 종료와 서비스 정리 기준

> 구현일: 2026-07-17
> 대상: `RUN/start_servers.bat`, `tools/server_control/`

## 목적

서버 관리 프로그램을 닫았는데 Docker 서비스나 Windows 호스트의 Streamlit이 계속 남는 상황을 방지한다. 서버 관리 GUI를 실행한 사용자가 프로그램을 종료하면 이 프로젝트가 시작한 서버도 함께 종료하는 것을 기본 동작으로 한다.

## 정상 종료

우상단 `X` 버튼을 누르면 GUI는 즉시 사라지지 않고 다음 순서로 처리한다.

1. 중복 종료 요청을 차단하고 창 제목을 `전체 서버 종료 중`으로 변경한다.
2. 실행 중인 Streamlit 프로세스와 그 하위 프로세스를 종료한다.
3. 현재 `_Total` 프로젝트의 `docker compose stop`을 실행한다.
4. 정상 종료 표식을 기록한다.
5. GUI 창을 닫는다.

정리 결과는 `_OUTPUT/logs/services/shutdown_guard.log`에 기록한다.

## 강제 종료 감시

`RUN/start_servers.bat`는 GUI를 직접 실행하지 않고 독립 종료 감시기 `tools/server_control/shutdown_guard.py`를 실행한다. 감시기가 GUI를 시작하고 종료 상태를 기다린다.

- GUI가 정상 종료 표식을 남기면 추가 종료 작업 없이 감시기를 끝낸다.
- 작업 관리자 등으로 GUI만 강제 종료되어 정상 표식이 없으면 감시기가 남은 Streamlit과 Docker Compose 서비스를 대신 종료한다.
- 실행 중인 Streamlit PID는 `_OUTPUT/logs/services/runtime/`의 임시 상태 파일로 전달한다.
- 감시가 끝나면 임시 상태 파일과 정상 종료 표식을 삭제한다.

## 보장 범위와 한계

- 우상단 `X`와 GUI 프로세스만 강제로 종료하는 일반적인 작업 관리자 종료는 처리할 수 있다.
- GUI와 독립 감시기를 동시에 종료하거나 전체 프로세스 트리를 강제 종료하면 정리 작업을 보장할 수 없다.
- 컴퓨터 전원 차단, 운영체제 강제 종료, Docker Desktop 자체 오류에서는 종료 작업을 보장할 수 없다.
- 감시기는 다른 프로젝트의 컨테이너를 종료하지 않고 현재 `_Total` 폴더의 Docker Compose 서비스만 정리한다.
- 서버 관리 GUI를 `main.py`로 직접 실행하면 `X` 정상 종료는 동작하지만 강제 종료 감시는 적용되지 않는다. 강제 종료 보호가 필요하면 `RUN/start_servers.bat` 또는 `RUN/start_servers_hidden.vbs`를 사용한다.

## 검증 기준

- 런처가 GUI 대신 종료 감시기를 시작하는지 확인한다.
- GUI에 Windows 창 닫기 처리기가 등록되어 있는지 확인한다.
- 종료 함수가 기록된 Streamlit PID의 프로세스 트리와 현재 프로젝트의 Docker Compose 서비스를 정리하는지 외부 실행을 대체한 테스트로 확인한다.
- 실제 종료 시험을 수행할 때는 다른 작업이 해당 서버를 사용하고 있지 않은지 먼저 확인한다.
