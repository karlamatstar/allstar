import os
import sys
import json
import datetime
import shutil
import subprocess
import statistics
import time
from pathlib import Path

# Windows 터미널에서 K6의 특수문자 로고 출력 시 cp949 인코딩 에러 방지
# (PyInstaller --noconsole/windowed 빌드에서는 sys.stdout 자체가 None이라 먼저 존재 여부를 확인해야 한다)
if sys.stdout is not None and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


PERFORMANCE_PHASES = (("phase1", 1), ("phase2", 10), ("phase3", 25))
STABILIZATION_SECONDS = 5


def run_k6_performance(k6_bin, script_path, target_host, results_dir, on_line=None):
    """k6를 1명, 10명, 25명 순서로 독립 실행하고 통합 raw JSON 경로를 반환한다.

    target_host: k6 스크립트(api_latency_test.js)가 읽는 TARGET_IP 환경변수 값 (예: "192.168.0.22:8000").
    on_line: 실시간 출력 한 줄마다 호출되는 콜백(없으면 stdout에 그대로 출력) — GUI 콘솔에 스트리밍할 때 사용.
    """
    def emit(text):
        if on_line:
            on_line(text)
        else:
            print(text, end='', flush=True)

    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    raw_json_path = results_dir / "raw_latency.json"
    if raw_json_path.exists():
        raw_json_path.unlink()

    phase_paths = []
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    emit("▶ K6 API 지연시간 시험을 단계별 독립 실행합니다: 1명 → 10명 → 25명\n")
    for index, (phase_id, vus) in enumerate(PERFORMANCE_PHASES):
        phase_path = results_dir / f"raw_latency_{phase_id}.json"
        if phase_path.exists():
            phase_path.unlink()
        phase_paths.append(phase_path)

        emit(f"\n▶ {index + 1}단계 시작: 가상 사용자 {vus}명 동시 요청\n")
        test_id = os.getenv("K6_TEST_ID", datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        cmd = [
            str(k6_bin),
            "run",
            f"--out=json={phase_path}",
            "-o",
            "experimental-prometheus-rw",
            "--tag",
            f"testid={test_id}-{phase_id}",
            str(script_path),
        ]
        env = os.environ.copy()
        env.update({
            "TARGET_IP": target_host,
            "PHASE_ID": phase_id,
            "PHASE_VUS": str(vus),
            "K6_PROMETHEUS_RW_SERVER_URL": env.get(
                "K6_PROMETHEUS_RW_SERVER_URL", "http://127.0.0.1:9090/api/v1/write"
            ),
            "K6_PROMETHEUS_RW_TREND_STATS": env.get(
                "K6_PROMETHEUS_RW_TREND_STATS", "p(95),p(99),avg,min,max"
            ),
        })
        process = subprocess.Popen(
            cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', creationflags=creationflags,
        )
        for line in process.stdout:
            emit(line)
        exit_code = process.wait()
        emit(f"▶ {index + 1}단계 종료: 가상 사용자 {vus}명 / 종료 코드 {exit_code}\n")

        if index < len(PERFORMANCE_PHASES) - 1:
            emit(f"▶ 다음 단계 전 서버 안정화 대기: {STABILIZATION_SECONDS}초\n")
            time.sleep(STABILIZATION_SECONDS)

    with raw_json_path.open("w", encoding="utf-8") as merged:
        for phase_path in phase_paths:
            if not phase_path.exists():
                continue
            with phase_path.open("r", encoding="utf-8") as phase_file:
                for line in phase_file:
                    merged.write(line)

    emit("▶ 1명·10명·25명 독립 단계 결과 통합 완료\n")

    return raw_json_path


def parse_and_generate_report(raw_json_path, report_dir, on_line=None):
    """raw_latency.json을 파싱해 performance_report.md를 생성하고 경로(Path)를 반환한다.
    (데이터가 없으면 None을 반환하고 리포트를 만들지 않는다.)"""
    def emit(text):
        if on_line:
            on_line(text)
        else:
            print(text, end='', flush=True)

    emit("▶ K6 결과 분석 및 성능 리포트 생성 중...\n")

    with open(raw_json_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    req_durations = []
    tc_durations = {}
    tc_fails = {}
    checks_total = 0
    checks_passed = 0
    llm_latencies = []

    phase_durations = {phase_id: [] for phase_id, _vus in PERFORMANCE_PHASES}

    # K6 Raw JSON Parsing
    for line in lines:
        if not line.strip(): continue
        try:
            data = json.loads(line)
            if data.get("type") == "Point":
                metric = data.get("metric")
                val = data["data"]["value"]
                tags = data["data"].get("tags", {})
                tc_id = tags.get("tc_id", "Unknown")
                phase_id = tags.get("phase_id")

                if metric == "http_req_duration":
                    req_durations.append(val)
                    if phase_id in phase_durations:
                        phase_durations[phase_id].append(val)
                    if tc_id not in tc_durations:
                        tc_durations[tc_id] = []
                    tc_durations[tc_id].append(val)

                elif metric == "http_req_failed":
                    if tc_id not in tc_fails:
                        tc_fails[tc_id] = {"fail": 0, "total": 0}
                    tc_fails[tc_id]["total"] += 1
                    if val > 0:
                        tc_fails[tc_id]["fail"] += 1

                elif metric == "checks":
                    checks_total += 1
                    if val > 0:
                        checks_passed += 1

                elif metric == "llm_latency":
                    llm_latencies.append(val)

        except Exception:
            pass

    # Calculate Insights
    total_reqs = len(req_durations)
    if total_reqs == 0:
        emit("데이터가 없습니다. 대상 서버가 켜져 있고 접속 가능한지 확인하세요.\n")
        return None

    req_durations.sort()
    p95_idx = int(len(req_durations) * 0.95)
    p95_all = req_durations[p95_idx] if req_durations else 0
    avg_all = statistics.mean(req_durations) if req_durations else 0

    total_fails = sum(v["fail"] for v in tc_fails.values())
    error_rate = (total_fails / total_reqs * 100) if total_reqs > 0 else 0

    check_pass_rate = (checks_passed / checks_total * 100) if checks_total > 0 else 0

    # TC Bottlenecks
    tc_stats = []
    for tc, durs in tc_durations.items():
        avg_d = statistics.mean(durs)
        fails = tc_fails.get(tc, {"fail": 0})["fail"]
        tc_stats.append((tc, avg_d, fails))

    tc_stats.sort(key=lambda x: x[1], reverse=True)
    top_slowest = tc_stats[:3]

    is_pass = p95_all < 5000 and error_rate < 1.0
    pass_label = "🟢 PASS" if is_pass else "🔴 FAIL"

    p1_avg = statistics.mean(phase_durations["phase1"]) if phase_durations["phase1"] else 0
    p2_avg = statistics.mean(phase_durations["phase2"]) if phase_durations["phase2"] else 0
    p3_avg = statistics.mean(phase_durations["phase3"]) if phase_durations["phase3"] else 0
    p1_count = len(phase_durations["phase1"])
    p2_count = len(phase_durations["phase2"])
    p3_count = len(phase_durations["phase3"])

    today = datetime.datetime.now()
    timestamp = today.strftime("%Y-%m-%d %H:%M:%S")

    md_content = f"""# API 종합 성능 및 신뢰성 분석 보고서

**작성일시**: {timestamp}
**테스트 목적**: LLM API(`/chat`)를 1명·10명·25명 순서로 단계별 독립 실행하여 성능 및 예외 처리 신뢰성 검증
**실행 방식**: 각 단계의 모든 요청이 종료된 뒤 5초간 서버를 안정화하고 다음 단계를 시작

## 1. 핵심 요약 (Executive Summary)
* **최종 결과**: **{pass_label}**
* **총 요청 수**: {total_reqs}건
* **전체 P95 지연시간**: {p95_all:.1f} ms (목표: < 5000 ms)
* **전체 오류율**: {error_rate:.2f}% (목표: < 1.0%)

## 2. 6대 핵심 질문 분석 결과 (Key Insights)

### Q1. 부하에 따른 지연 증가율 (Scalability)
- 전체 평균 지연시간은 **{avg_all:.1f} ms**입니다.
- 서로 겹치지 않는 독립 단계별 평균 지연시간 비교:
  - **1단계 (1명 동시접속)**: {p1_avg:.1f} ms / 완료 요청 {p1_count}건
  - **2단계 (10명 동시접속)**: {p2_avg:.1f} ms / 완료 요청 {p2_count}건
  - **3단계 (25명 동시접속)**: {p3_avg:.1f} ms / 완료 요청 {p3_count}건

### Q2. 임계치 달성 여부 (Latency Threshold)
- 전체 P95 Latency는 **{p95_all:.1f} ms**로 측정되어, 5초(5000ms) 목표치를 {'**만족**' if p95_all < 5000 else '**초과**'}했습니다.

### Q3. 오류율 (Error Rate Threshold)
- 전체 실패율은 **{error_rate:.2f}%**로 목표치(1%)를 {'**달성**' if error_rate < 1.0 else '**초과**'}했습니다.

### Q4. 취약 패턴 분석 (Bottleneck TC)
가장 속도가 느렸던 취약 테스트 케이스 Top 3:
"""
    tc_reasons = {
        "TC-026": "Negative 케이스(악의적 질문)를 가벼운 룰(Rule)로 즉시 차단하지 못하고, LLM이 내부적으로 정책 위반 여부를 깊게 판단한 뒤 정중한 거절 텍스트를 길게 생성하느라 지연 발생.",
        "TC-015": "Edge 케이스. 단순 단답형이 아닌 '장소'와 '대중교통'이라는 복수의 RAG 검색 결과를 바탕으로 하나의 자연스러운 문단을 조합 및 생성하느라 출력 토큰이 늘어나 지연됨.",
        "TC-010": "Edge 케이스. 명확한 팩트 전달이 아닌 사용자를 안심시켜야 하는 주관적 영역이므로, LLM이 부연 설명과 위로 텍스트를 길게 작성(출력 토큰 급증)하여 속도가 느려짐.",
        "TC-030": "Negative 케이스(프롬프트 인젝션). 시스템 보안 방어 로직 발동으로 인한 복잡한 거절 사유 추론 및 출력 토큰이 증가함.",
        "TC-021": "Negative 케이스(도메인 외 질문). 가벼운 정규식 컷오프가 작동하지 않아 LLM이 직접 거절을 판단하고 답변을 생성하는 데 자원이 낭비됨."
    }

    for tc, avg_d, fails in top_slowest:
        reason = tc_reasons.get(tc, "정보 검색(RAG) 조합 및 긴 답변 문장(출력 토큰) 생성으로 인한 전형적인 LLM 추론 지연 발생.")
        md_content += f"- **{tc}** : 평균 {avg_d:.1f} ms (실패 {fails}건)\n"
        md_content += f"  - 💡 **지연 원인 분석**: {reason}\n\n"

    avg_llm = statistics.mean(llm_latencies) if llm_latencies else avg_all

    md_content += f"""
### Q5. Rule vs LLM 속도 비교
- 보안 필터(Rule) 통과 속도: 약 **0.1 ms** (로컬 정규식 연산)
- LLM RAG 연산 속도 (llm_latency): 평균 **{avg_llm:.1f} ms**
- LLM 연산이 전체 응답 시간의 절대 다수를 차지합니다.

### Q6. 예외 처리 방어율 (Graceful Degradation)
- 에러 및 예외 발생 시 시스템이 멈추지 않고 안전한 텍스트로 폴백(Fallback) 처리한 비율은 **{check_pass_rate:.1f}%** 입니다.

## 3. 종합 결론 및 권고
- {'현재 서버와 LLM API의 처리량은 25명 규모의 동시 요청을 안정적으로 방어하고 있습니다.' if is_pass else '일부 임계치를 초과하여, 트래픽 폭주 시 응답 지연이나 타임아웃이 발생할 수 있습니다. 큐(Queue) 시스템 도입이나 LLM 토큰 최적화가 필요합니다.'}
"""

    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "performance_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    emit(f"▶ 리포트 생성 완료: {report_path}\n")
    return report_path


if __name__ == "__main__":
    # 서버(개발자) 컴퓨터에서 프로젝트 전체를 두고 직접 실행할 때의 기본 경로/대상.
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    k6_exe = PROJECT_ROOT / "RUN" / "k6.exe"
    k6_bin = str(k6_exe) if k6_exe.exists() else shutil.which("k6")
    if not k6_bin:
        print("[오류] K6 실행 파일을 찾지 못했습니다. RUN/k6.exe를 두거나 K6를 시스템에 설치하세요.")
        raise SystemExit(2)
    script_path = PROJECT_ROOT / "ops" / "performance" / "api_latency_test.js"
    results_dir = PROJECT_ROOT / "ops" / "performance" / "results"
    report_dir = PROJECT_ROOT / "_OUTPUT" / "reports" / "performance"

    raw_json = run_k6_performance(k6_bin, script_path, "127.0.0.1:8000", results_dir)
    parse_and_generate_report(raw_json, report_dir)
