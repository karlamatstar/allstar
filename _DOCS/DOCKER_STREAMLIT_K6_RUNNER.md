# Docker Streamlit과 K6 전용 실행 서비스

> 구현일: 2026-07-18
> 적용 대상: `_Total` 로컬 Docker Compose
> 상태: **구현·로컬 실행·중지·비과금 검증 완료**

## 결정

통합 Streamlit은 `streamlit` 컨테이너에서 실행하고 K6는 별도의 `k6-runner` 컨테이너에서 실행한다. 이 구조는 AWS 배포를 전제로 하지 않는다. 현재 개발 컴퓨터의 Docker Desktop만으로 전체 기능을 실행할 수 있으며, AWS는 외부 공개가 실제로 필요해질 때 별도 운영·보안 검토 후 선택한다.

```text
웹브라우저
   ↓ :8501
Streamlit 컨테이너
   ↓ 허용된 시험 ID와 설정값만 전달
K6 전용 실행 서비스 :8200
   ├─ Linux K6 2.1.0
   ├─ AI API·Prometheus 내부 주소 사용
   └─ _OUTPUT에 실행 로그·결과 저장
```

Windows의 `k6.exe`는 Linux 컨테이너에서 사용하지 않는다. K6 전용 이미지는 공식 `grafana/k6:2.1.0`에서 Linux 실행 파일을 가져온다. QA 컨트롤러를 Windows에서 직접 실행할 때는 기존처럼 `RUN/k6.exe` 또는 Windows PATH의 K6를 사용하는 호스트 대체 경로를 유지한다.

## 서비스 구성

| 서비스 | 주소 | 역할 |
|---|---|---|
| Streamlit | `http://localhost:8501` | 통합 대시보드와 K6 실행 화면 |
| K6 Runner | `http://127.0.0.1:8200` | 허용된 7개 시험의 시작·상태·중지 |
| 채팅 서비스 제어 | 내부 `service-control:8300` | AI·VOC 채팅 API의 제한된 시작·중단 |

K6 Runner 포트는 로컬 호스트에만 공개한다. 임의 명령 문자열은 받지 않으며 코드에 등록된 시험 ID만 실행한다. 서버 연결 성능 종합 시험은 `actual_api_confirmed=true`가 없으면 HTTP 403으로 거부한다. 한 번에 하나의 시험만 허용하고 실행 로그는 `_OUTPUT/logs/qa/runs/`에 계속 누적한다.

## 데이터 보존

- Streamlit과 K6 Runner는 같은 호스트 `_OUTPUT`을 `/srv/app/_OUTPUT`으로 공유한다.
- AI·VOC 테스트케이스 JSON은 호스트 원본 파일을 두 컨테이너에 연결한다.
- 화면에서 테스트케이스를 수정하면 Git 작업 폴더의 원본 JSON에 즉시 반영된다.
- 수정·삭제 전 이력은 `_OUTPUT/archives/testcases/ai_agent/`와 `_OUTPUT/archives/testcases/voc/`에 보존한다.
- 컨테이너를 재생성해도 로그·보고서·테스트케이스와 수정 이력이 유지된다.

## 시작과 종료

서버 관리에서 `전체 시작`을 누르면 `docker compose up -d --build`가 Streamlit과 K6 Runner까지 함께 시작한다. 브라우저는 자동으로 열지 않으며 `통합 대시보드` 바로가기로 접속한다.

`서버 전체 종료`는 현재 프로젝트의 모든 Compose 서비스를 중지하고 Docker Desktop은 유지한다. `Docker 포함 전체 종료`만 Docker Desktop까지 종료한다. 8501 포트의 Docker Desktop 프록시 프로세스는 Windows 호스트 Streamlit으로 오인해 강제 종료하지 않는다.

## 현재 제한과 AWS 전환 기준

Docker 내부 Streamlit에는 Docker 소켓을 연결하지 않는다. AI·VOC 채팅 서버의 중단·재접속은 Streamlit과 분리된 제한형 `service-control` 브리지가 담당한다. 브리지는 호스트 포트를 공개하지 않고 `portfolio-api`와 `voc-api`만 제어한다. 상세 허용 범위는 `CHAT_SERVICE_CONTROL_BRIDGE.md`를 따른다.

AWS 또는 외부 공개 배포는 필수가 아니다. 전환할 때는 다음을 별도로 결정한다.

- HTTPS와 사용자 인증
- QA·부하 시험 실행 권한과 동시 실행 제한
- 컨테이너 서비스 제어 API의 최소 권한
- Prometheus 보존 기간, Grafana 접근 권한과 알림
- 로그·보고서 영구 저장소와 백업

## 2026-07-18 검증 결과

- Compose 구성 검사와 Streamlit·K6 Runner 이미지 빌드 성공
- AI·VOC API, Streamlit, K6 Runner, Prometheus, Grafana Health HTTP 200 확인
- K6 Runner에서 Linux K6 `2.1.0` 확인
- 기본 동작 시험 정상 완료 및 Prometheus remote write·공유 로그 확인
- 일반 부하 시험 실행 중 중지 후 `cancelled` 상태와 로그 보존 확인
- 실제 API 확인 없이 서버 연결 성능 종합 시험 요청 시 HTTP 403 확인
- 장애·기능 검증: K6 종료 코드 0, 기능 시험 `283개 통과·2개 환경상 건너뜀·2개 선택 제외`, 전체 종료 코드 0
- 실패·중지 시 정식 장애 보고서를 갱신하지 않고 정상 완료 때만 갱신하는 동작 확인
- 이 검증에서는 외부 AI API를 호출하지 않음
- 최소 패키지 `service-control` 이미지 빌드, 내부 Health 200, 호스트 포트 미공개, 비허용 서비스 HTTP 403 확인
- 브리지 기반 AI 실제 중단·Health 연결 실패·재시작 후 HTTP 200 복원과 대시보드 재접속 완료 자동 전환 확인
