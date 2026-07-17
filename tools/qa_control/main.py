from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from allstar.shared.qa_reporting import QAReportSession
from allstar.shared.single_instance import DUPLICATE_INSTANCE_EXIT_CODE, SingleInstanceLock

PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
PY = str(PYTHON if PYTHON.exists() else sys.executable)
LOG_DIR = ROOT / "_OUTPUT" / "logs" / "services" / "launcher"
LOG_DIR.mkdir(parents=True, exist_ok=True)
RUN_LOG = LOG_DIR / "qa_control_runs.jsonl"
RUN_LOG_LOCK = threading.Lock()
VOC_TEST_CASES_PATH = ROOT / "src" / "allstar" / "voc" / "evaluation" / "test_cases.json"
AI_TEST_CASES_PATH = ROOT / "src" / "allstar" / "ai_agent" / "evaluation" / "test_cases.json"

AI_TESTS = [
    ("기본 동작 시험 (Smoke Test)", ["k6", "run", "ops/performance/smoke_test.js"], False),
    ("일반 부하 시험 (Load Test)", ["k6", "run", "ops/performance/load_test.js"], True),
    ("무작위 요청 시험 (Random Test)", ["k6", "run", "ops/performance/random_test.js"], True),
    ("한계 부하 시험 (Stress Test)", ["k6", "run", "ops/performance/stress_test.js"], True),
    ("순간 급증 시험 (Spike Test)", ["k6", "run", "ops/performance/spike_test.js"], True),
    ("장애·기능 검증 시험 (Validation Test)", [PY, "-u", "tools/scripts/run_validation_tests.py"], True),
    ("서버 연결 성능 종합 시험 (API)", [PY, "-u", "tools/scripts/run_performance_tests.py"], True),
    ("테스트케이스 품질 시험 (Test Case Test)", [PY, "-u", "-m", "allstar.ai_agent.evaluation.quality_pipeline"], True),
]

LOAD_SETTINGS = {
    "일반 부하 시험 (Load Test)": ("20", "60"),
    "무작위 요청 시험 (Random Test)": ("100", "60"),
    "한계 부하 시험 (Stress Test)": ("100", "120"),
    "순간 급증 시험 (Spike Test)": ("200", "60"),
}

TEST_IDS = {
    "기본 동작 시험 (Smoke Test)": "ai_smoke",
    "일반 부하 시험 (Load Test)": "ai_load",
    "무작위 요청 시험 (Random Test)": "ai_random",
    "한계 부하 시험 (Stress Test)": "ai_stress",
    "순간 급증 시험 (Spike Test)": "ai_spike",
    "장애·기능 검증 시험 (Validation Test)": "ai_validation",
    "서버 연결 성능 종합 시험 (API)": "ai_api_performance",
    "테스트케이스 품질 시험 (Test Case Test)": "ai_testcase",
    "전체 비AI pytest": "voc_non_ai",
    "단위 테스트": "voc_unit",
    **{f"에이전트 교차 테스트 ({profile_id})": f"voc_profile_{profile_id.lower()}" for profile_id in "ABCD"},
}

K6_REQUIRED_TEST_IDS = {
    "ai_smoke",
    "ai_load",
    "ai_random",
    "ai_stress",
    "ai_spike",
    "ai_validation",
    "ai_api_performance",
}
GRAFANA_ONLY_K6_TEST_IDS = {
    "ai_smoke",
    "ai_load",
    "ai_random",
    "ai_stress",
    "ai_spike",
}
K6_INSTALL_URL = "https://grafana.com/docs/k6/latest/set-up/install-k6/"

TEST_DESCRIPTIONS = {
    "기본 동작 시험 (Smoke Test)": (
        "K6 부하 시험 도구로 가상 사용자 1명이 서버 상태와 모의 채팅을 각각 한 번 호출하는 가장 가벼운 시험입니다.\n"
        "서버가 켜져 있는지, 기본 연결과 HTTP 200 응답이 정상인지 빠르게 확인할 수 있습니다. "
        "결과는 Prometheus로 자동 전송되어 Grafana에서 확인하며 별도 사용자용 보고서는 생성하지 않습니다."
    ),
    "일반 부하 시험 (Load Test)": (
        "K6 부하 시험 도구로 설정한 가상 인원이 일정 시간 동안 모의 채팅 요청을 계속 보내는 일상 부하 시험입니다.\n"
        "지속적인 요청에서 응답 지연, 실패율, 처리 안정성이 기준을 유지하는지 확인합니다. "
        "결과는 Prometheus로 자동 전송되어 Grafana에서 확인하며 별도 사용자용 보고서는 생성하지 않습니다."
    ),
    "무작위 요청 시험 (Random Test)": (
        "K6 부하 시험 도구가 가상 인원 수를 1초마다 1명부터 설정한 최댓값 사이에서 무작위로 바꾸는 변동 부하 시험입니다.\n"
        "예측하기 어려운 요청 증감에서 서버가 안정적으로 응답하는지 확인합니다. "
        "결과는 Prometheus로 자동 전송되어 Grafana에서 확인하며 별도 사용자용 보고서는 생성하지 않습니다."
    ),
    "한계 부하 시험 (Stress Test)": (
        "K6 부하 시험 도구로 가상 인원을 단계적으로 늘려 최댓값을 유지한 뒤 다시 낮추는 한계 부하 시험입니다.\n"
        "서버의 처리 한계, 고부하 구간의 오류, 부하 감소 후 회복 여부를 확인합니다. "
        "결과는 Prometheus로 자동 전송되어 Grafana에서 확인하며 별도 사용자용 보고서는 생성하지 않습니다."
    ),
    "순간 급증 시험 (Spike Test)": (
        "K6 부하 시험 도구로 가상 인원을 짧은 시간에 최댓값까지 급격히 올렸다가 다시 낮추는 순간 폭주 시험입니다.\n"
        "갑작스러운 트래픽 급증을 견디는지와 급증 종료 후 정상 상태로 복구되는지 확인합니다. "
        "결과는 Prometheus로 자동 전송되어 Grafana에서 확인하며 별도 사용자용 보고서는 생성하지 않습니다."
    ),
    "장애·기능 검증 시험 (Validation Test)": (
        "K6 부하 시험 도구로 지연·서버 오류·시간 초과 같은 장애 상황을 재현하고 전체 기능 검사를 함께 수행합니다.\n"
        "장애 대응과 기존 기능의 정상 동작을 한 번에 확인하며, 완료 후 결함 보고서가 자동 생성됩니다."
    ),
    "서버 연결 성능 종합 시험 (API)": (
        "K6 부하 시험 도구로 가상 사용자 1명, 10명, 25명 순서로 서버 연결 통로(API)에 실제 채팅 요청을 보내는 성능 시험입니다.\n"
        "각 단계가 완전히 끝난 뒤 5초간 안정화하고 다음 단계를 시작하는 단계별 독립 실행 방식이며, "
        "응답시간과 실패율 변화를 확인할 수 있습니다. 완료 후 성능 보고서가 자동 생성됩니다."
    ),
    "테스트케이스 품질 시험 (Test Case Test)": (
        "현재 등록된 AI 에이전트 테스트케이스 전체를 규칙 기반 답변과 API 기반 답변으로 각각 실행하고 품질을 비교합니다.\n"
        "실행 범위와 외부 AI 비용을 확인한 뒤 시작하며, 정상 완료 시 기존 AI 에이전트 테스트케이스 보고서와 그래프가 자동 갱신됩니다."
    ),
}

VOC_NON_AI_DESCRIPTION = (
    "외부 AI를 호출하지 않고 VOC 에이전트, 독립 평가, 보고서 생성 로직을 전체적으로 검사합니다.\n"
    "빠르게 코드 회귀와 기본 데이터 흐름의 이상 여부를 확인하며, 시험 결과는 자동 정리됩니다."
)

VOC_UNIT_DESCRIPTION = (
    "각 VOC 에이전트와 독립 품질 평가(Judge)를 작은 기능 단위로 나누어 검사합니다.\n"
    "문제가 발생했을 때 어느 기능에서 실패했는지 빠르게 찾을 수 있으며, 시험 결과는 자동 정리됩니다."
)

VOC_PROFILE_DESCRIPTION = (
    "등록된 VOC 테스트케이스 전체를 선택한 A~D 모델 조합으로 실행해 답변 생성과 독립 품질 평가를 함께 확인합니다.\n"
    "멀티 에이전트 처리 과정, 최종 답변, 평가 결과를 기록하며 완료 후 프로필별 보고서가 자동 생성됩니다."
)

PROFILE_LABELS = {
    "A": "답변 생성: OpenAI / gpt-5.6-luna / 추론 끔(none)\n독립 품질 평가(Judge): Anthropic / claude-sonnet-5 / 낮음(low)",
    "B": "답변 생성: Anthropic / claude-sonnet-4-6 / 낮음(low)\n독립 품질 평가(Judge): OpenAI / gpt-5.6-terra / 낮음(low)",
    "C": "답변 생성: OpenAI / gpt-5.6-luna / 추론 끔(none)\n독립 품질 평가(Judge): OpenAI / gpt-5.6-terra / 낮음(low)",
    "D": "답변 생성: Anthropic / claude-sonnet-4-6 / 낮음(low)\n독립 품질 평가(Judge): Anthropic / claude-sonnet-5 / 낮음(low)",
}


def two_line_tab_label(title: str) -> str:
    """끝의 영문 괄호 표기를 탭 둘째 줄로 내린다."""
    if title.endswith(")") and " (" in title:
        korean, parenthesized = title.rsplit(" (", 1)
        return f"{korean}\n({parenthesized}"
    return title


def load_voc_case_counts() -> tuple[int, int]:
    """현재 VOC 테스트케이스 전체 수와 실제 LLM 평가 대상 수를 반환한다."""
    try:
        cases = json.loads(VOC_TEST_CASES_PATH.read_text(encoding="utf-8"))["cases"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return 0, 0
    return len(cases), sum(bool(case.get("judge_enabled", False)) for case in cases)


def load_ai_case_count() -> int:
    """현재 등록된 AI 에이전트 테스트케이스 수를 반환한다."""
    try:
        cases = json.loads(AI_TEST_CASES_PATH.read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError):
        return 0
    return len(cases) if isinstance(cases, list) else 0


def find_k6() -> str | None:
    """프로젝트에 둔 실행 파일을 우선하고, 없으면 시스템 설치 경로를 찾는다."""
    bundled = ROOT / "RUN" / "k6.exe"
    if bundled.exists():
        return str(bundled)
    return shutil.which("k6")


def validate_load_settings(vus_text: str, duration_text: str) -> tuple[int, int]:
    try:
        vus = int(vus_text)
        duration = int(duration_text)
    except ValueError as error:
        raise ValueError("가상 인원과 실행 시간은 숫자로 입력하세요.") from error
    if vus < 1:
        raise ValueError("가상 인원은 1명 이상이어야 합니다.")
    if duration < 1:
        raise ValueError("실행 시간은 1초 이상이어야 합니다.")
    return vus, duration


def append_run_event(event: dict) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG_LOCK, RUN_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(event, ensure_ascii=False) + "\n")


class TestTab(tk.Frame):
    def __init__(
        self,
        parent,
        title: str,
        command: list[str],
        confirm: bool = False,
        detail: str = "",
        load_settings: tuple[str, str] | None = None,
        owner: "QAControl | None" = None,
        test_id: str | None = None,
    ):
        super().__init__(parent, bg="#202634")
        self.owner = owner
        self.title_text = title
        self.test_id = test_id or TEST_IDS[title]
        self.command = command
        self.confirm = confirm
        self.process: subprocess.Popen | None = None
        self.cancel_requested = False
        self.started_at: str | None = None
        self.report_session: QAReportSession | None = None
        self.vus_var = tk.StringVar(value=load_settings[0]) if load_settings else None
        self.duration_var = tk.StringVar(value=load_settings[1]) if load_settings else None
        tk.Label(self, text=title, bg="#202634", fg="#e5ebf5",
                 font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=12, pady=(12, 4))
        tk.Label(
            self,
            text=detail or "이 시험의 실행 방식과 확인 항목을 준비 중입니다.",
            bg="#202634",
            fg="#9aa9bf",
            justify="left",
            anchor="w",
            wraplength=1240,
            font=("Malgun Gothic", 9),
        ).pack(fill="x", anchor="w", padx=12)
        if load_settings:
            settings = tk.Frame(self, bg="#202634")
            settings.pack(fill="x", padx=12, pady=(10, 0))
            tk.Label(settings, text="최대 가상 인원 (VU):", bg="#202634", fg="#e5ebf5").pack(side="left")
            tk.Entry(settings, textvariable=self.vus_var, width=10, justify="center").pack(side="left", padx=(6, 18))
            tk.Label(settings, text="실행 시간 (초):", bg="#202634", fg="#e5ebf5").pack(side="left")
            tk.Entry(settings, textvariable=self.duration_var, width=10, justify="center").pack(side="left", padx=6)
        bar = tk.Frame(self, bg="#202634")
        bar.pack(fill="x", padx=12, pady=9)
        self.start_button = tk.Button(bar, text="실행", command=self.start, bg="#26734d", fg="white", relief="flat", padx=15)
        self.start_button.pack(side="left")
        self.stop_button = tk.Button(
            bar, text="중지", command=self.stop, bg="#8a3142", fg="white",
            disabledforeground="#a7adb8", relief="flat", padx=15, state="disabled",
        )
        self.stop_button.pack(side="left", padx=6)
        self.console = tk.Text(self, bg="#0f131c", fg="#d8e1ef", font=("Consolas", 9), wrap="word")
        self.console.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def start(self):
        if self.process and self.process.poll() is None:
            messagebox.showinfo("실행 중", "이미 테스트가 실행 중입니다.")
            return
        k6_bin = find_k6() if self.test_id in K6_REQUIRED_TEST_IDS else None
        if self.test_id in K6_REQUIRED_TEST_IDS and not k6_bin:
            message = (
                "K6 부하 시험 도구가 설치되어 있지 않아 시험을 실행할 수 없습니다.\n\n"
                "Grafana K6 공식 설치 페이지에서 K6를 다운로드·설치한 뒤 "
                "QA 컨트롤러를 다시 실행하세요.\n\n"
                f"공식 설치 안내: {K6_INSTALL_URL}\n\n"
                "공식 설치 페이지를 지금 열까요?"
            )
            self.console.insert("end", "\n[K6 실행 불가] " + message.replace("\n\n", " ").replace("\n", " ") + "\n")
            self.console.see("end")
            if messagebox.askyesno("K6 설치 필요", message):
                webbrowser.open(K6_INSTALL_URL)
            return
        env = os.environ.copy()
        load_summary = ""
        report_settings: dict[str, str | int] = {}
        if self.vus_var and self.duration_var:
            try:
                vus, duration = validate_load_settings(self.vus_var.get(), self.duration_var.get())
            except ValueError as error:
                messagebox.showerror("입력값 확인", str(error))
                return
            env["K6_VUS"] = str(vus)
            env["SCRIPT_DURATION"] = str(duration)
            env["TARGET_IP"] = "127.0.0.1:8000"
            load_summary = f"설정: 최대 가상 인원 {vus}명 / 실행 시간 {duration}초\n"
            report_settings.update({"최대 가상 인원(VU)": vus, "실행 시간(초)": duration})
        if self.confirm:
            message = (
                f"대상: http://localhost:8000\n{load_summary}"
                "부하·장애 또는 실제 AI 호출이 포함될 수 있습니다.\n"
                "다른 파괴적 테스트가 실행 중이지 않은지 확인했습니까?"
            )
            if "run_voc_profile.py" in " ".join(self.command):
                total_cases, api_cases = load_voc_case_counts()
                max_api_calls = api_cases * 7
                message = (
                    "실험군: " + self.test_id[-1].upper() + "\n"
                    f"등록된 전체 테스트케이스: {total_cases}건\n"
                    f"실제 AI 평가 대상: {api_cases}건\n"
                    f"예상 외부 AI 기본 호출: 평가 대상당 최대 7회, 총 최대 {max_api_calls}회\n"
                    "API 재시도가 발생하면 실제 호출 수는 더 늘어날 수 있습니다.\n"
                    "실제 외부 AI 연결 시험(API)을 실행할까요?"
                )
            elif self.test_id == "ai_api_performance":
                message = (
                    "대상: http://localhost:8000\n"
                    "실행 단계: 1명 → 10명 → 25명 (단계별 독립 실행)\n"
                    "단계 사이 안정화: 5초\n"
                    "예상 실제 채팅 요청: 정상 완료 시 총 36건\n"
                    "실제 외부 AI 호출이 포함됩니다. 성능 시험을 실행할까요?"
                )
            elif self.test_id == "ai_testcase":
                total_cases = load_ai_case_count()
                max_api_calls = total_cases * 3
                message = (
                    f"등록된 전체 테스트케이스: {total_cases}건\n"
                    "실행 방식: 규칙 기반 답변과 API 기반 답변 비교 평가\n"
                    f"예상 외부 AI 기본 호출: 케이스당 최대 3회, 총 최대 {max_api_calls}회\n"
                    "API 재시도가 발생하면 실제 호출 수는 더 늘어날 수 있습니다.\n"
                    "전체 테스트케이스 품질 시험을 실행할까요?"
                )
            if not messagebox.askyesno("실행 전 확인", message):
                return
        if self.owner and not self.owner.acquire_execution(self):
            return
        self.cancel_requested = False
        self.started_at = datetime.now().astimezone().isoformat(timespec="seconds")
        if self.test_id.startswith("voc_profile_"):
            total_cases, api_cases = load_voc_case_counts()
            report_settings.update({
                "프로필": self.test_id[-1].upper(),
                "전체 테스트케이스": total_cases,
                "실제 AI 평가 대상": api_cases,
            })
        if self.test_id == "ai_api_performance":
            report_settings.update({
                "실행 단계": "1명 → 10명 → 25명",
                "실행 방식": "단계별 독립 실행",
                "단계 사이 안정화": "5초",
                "최대 실제 채팅 요청": 36,
            })
        if self.test_id == "ai_testcase":
            total_cases = load_ai_case_count()
            report_settings.update({
                "전체 테스트케이스": total_cases,
                "예상 외부 AI 기본 호출": f"최대 {total_cases * 3}회",
            })
        report_command = list(self.command)
        if report_command and report_command[0].lower() == "k6" and k6_bin:
            report_command[0] = k6_bin
        self.report_session = QAReportSession(
            test_id=self.test_id,
            test_name=self.title_text,
            command=report_command,
            settings=report_settings,
            write_summary_report=self.test_id not in GRAFANA_ONLY_K6_TEST_IDS,
        )
        env.setdefault("K6_PROMETHEUS_RW_SERVER_URL", "http://127.0.0.1:9090/api/v1/write")
        env.setdefault("K6_PROMETHEUS_RW_TREND_STATS", "p(95),p(99),avg,min,max")
        env["K6_TEST_ID"] = self.report_session.run_id
        execution_command = self.report_session.command_for_execution()
        try:
            self.report_session.start()
        except Exception as error:
            self.console.insert("end", f"\n[로그 준비 실패] {error}\n")
            append_run_event(self._run_event("finished", "start_failed", error=str(error)))
            if self.owner:
                self.owner.release_execution(self)
            return
        self.console.insert("end", "\n> " + " ".join(execution_command) + "\n")
        if load_summary:
            self.console.insert("end", load_summary)
        append_run_event(self._run_event(
            "started", "running", settings=report_settings,
            run_id=self.report_session.run_id,
            log=str(self.report_session.log_path.relative_to(ROOT)),
        ))
        try:
            self.process = subprocess.Popen(
                execution_command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as error:
            self.console.insert("end", f"\n[시작 실패] {error}\n")
            try:
                report = self.report_session.finish("start_failed", None, error=str(error))
                append_run_event(self._run_event(
                    "finished", "start_failed", error=str(error),
                    run_id=self.report_session.run_id, report=report["report"],
                ))
            except Exception as report_error:
                self._append(f"[보고서 생성 실패] {report_error}\n")
                append_run_event(self._run_event(
                    "finished", "start_failed", error=str(error), report_error=str(report_error),
                ))
            finally:
                if self.owner:
                    self.owner.release_execution(self)
            return
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        assert self.process and self.process.stdout
        for line in self.process.stdout:
            if self.report_session:
                self.report_session.append_output(line)
            self.after(0, self._append, line)
        code = self.process.wait()
        status = "cancelled" if self.cancel_requested else "completed" if code == 0 else "failed"
        self.after(0, self._finish, status, code)

    def _run_event(self, event: str, status: str, **extra) -> dict:
        payload = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "event": event,
            "status": status,
            "test": self.title_text,
            "command": self.command,
            "started_at": self.started_at,
        }
        payload.update(extra)
        return payload

    def _finish(self, status: str, code: int):
        labels = {"completed": "완료", "failed": "실패", "cancelled": "사용자 중지"}
        self._append(f"\n[실행 상태: {labels[status]} / 종료 코드: {code}]\n")
        try:
            report = self.report_session.finish(status, code) if self.report_session else None
            append_run_event(self._run_event(
                "finished", status, exit_code=code,
                run_id=self.report_session.run_id if self.report_session else None,
                report=report["report"] if report else None,
            ))
        except Exception as error:
            self._append(f"[보고서 생성 실패] {error}\n")
            append_run_event(self._run_event("finished", status, exit_code=code, report_error=str(error)))
        finally:
            self.process = None
            if self.owner:
                self.owner.release_execution(self)

    def _append(self, text: str):
        self.console.insert("end", text)
        self.console.see("end")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.cancel_requested = True
            self._append("\n[사용자 중지 요청] 실행 중인 시험을 종료합니다.\n")
            pid = self.process.pid

            def worker():
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW, check=False)

            threading.Thread(target=worker, daemon=True).start()

    def set_execution_controls(self, active: bool, any_running: bool):
        self.start_button.configure(state="disabled" if any_running else "normal")
        self.stop_button.configure(state="normal" if active else "disabled")

class QAControl(tk.Tk):
    def __init__(self):
        super().__init__()
        self.test_tabs: list[TestTab] = []
        self.active_tab: TestTab | None = None
        self.title("AllStar 품질검사 관리")
        self.geometry("1320x800")
        self.minsize(1200, 650)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background="#151923")
        style.configure(
            "TNotebook.Tab",
            font=("Malgun Gothic", 9, "bold"),
            padding=(14, 9),
            anchor="center",
            justify="center",
            background="#2f3b52",
            foreground="#dbe6f5",
        )
        style.map(
            "TNotebook.Tab",
            padding=[("selected", (14, 9)), ("!selected", (14, 9))],
            background=[("selected", "#496080"), ("active", "#3b4a63")],
            foreground=[("selected", "#ffffff"), ("!selected", "#dbe6f5")],
        )
        top = ttk.Notebook(self)
        top.pack(fill="both", expand=True)
        ai = tk.Frame(top, bg="#202634")
        voc = tk.Frame(top, bg="#202634")
        top.add(ai, text="AI 상담 품질검사\n(AI Agent QA)")
        top.add(voc, text="고객 의견 분석 품질검사\n(VOC QA)")

        ai_tabs = ttk.Notebook(ai)
        ai_tabs.pack(fill="both", expand=True, padx=8, pady=8)
        for title, command, confirm in AI_TESTS:
            self._add_test_tab(
                ai_tabs,
                two_line_tab_label(title),
                title,
                command,
                confirm,
                detail=TEST_DESCRIPTIONS[title],
                load_settings=LOAD_SETTINGS.get(title),
            )

        voc_tabs = ttk.Notebook(voc)
        voc_tabs.pack(fill="both", expand=True, padx=8, pady=8)
        self._add_test_tab(
            voc_tabs, "전체 비AI 검사\n(pytest)",
            "전체 비AI pytest",
            [
                PY, "-u", "-m", "pytest", "tests/voc/evaluation", "-v",
                "--ignore=tests/voc/evaluation/test_pipeline_e2e.py",
                "-k", "not end_to_end",
            ],
            detail=VOC_NON_AI_DESCRIPTION,
        )
        self._add_test_tab(
            voc_tabs, "단위 테스트\n(Unit Test)",
            "단위 테스트",
            [PY, "-u", "-m", "pytest", "tests/voc/evaluation/test_agent_unit.py", "tests/voc/evaluation/test_llm_judge.py", "-v"],
            detail=VOC_UNIT_DESCRIPTION,
        )
        for profile_id in "ABCD":
            command = [PY, "-u", "tools/scripts/run_voc_profile.py", "--profile", profile_id]
            total_cases, api_cases = load_voc_case_counts()
            detail = (
                VOC_PROFILE_DESCRIPTION
                + "\n\n"
                + PROFILE_LABELS[profile_id]
                + f"\n현재 전체 {total_cases}건 중 실제 AI 평가 대상은 {api_cases}건입니다. "
                "확장 사고 기능: 사용 안 함(thinking=disabled)"
            )
            title = f"에이전트 교차 테스트 ({profile_id})"
            self._add_test_tab(
                voc_tabs, f"에이전트 교차 테스트\n({profile_id})",
                title, command, True, detail=detail,
            )

    def _add_test_tab(self, notebook, tab_text: str, title: str, command: list[str], confirm: bool = False, **kwargs):
        tab = TestTab(notebook, title, command, confirm, owner=self, test_id=TEST_IDS[title], **kwargs)
        self.test_tabs.append(tab)
        notebook.add(tab, text=tab_text)

    def acquire_execution(self, tab: TestTab) -> bool:
        if self.active_tab is not None:
            messagebox.showwarning(
                "시험 실행 중",
                f"'{self.active_tab.title_text}'이(가) 실행 중입니다.\n현재 시험을 중지하거나 완료한 뒤 다시 실행하세요.",
            )
            return False
        self.active_tab = tab
        for candidate in self.test_tabs:
            candidate.set_execution_controls(candidate is tab, any_running=True)
        return True

    def release_execution(self, tab: TestTab):
        if self.active_tab is tab:
            self.active_tab = None
        for candidate in self.test_tabs:
            candidate.set_execution_controls(active=False, any_running=False)


def main() -> int:
    instance = SingleInstanceLock("Local\\AllStarQAControlCenter")
    if not instance.acquire():
        messagebox.showwarning("이미 실행 중입니다", "품질검사 관리 프로그램이 이미 실행 중입니다.")
        return DUPLICATE_INSTANCE_EXIT_CODE
    try:
        QAControl().mainloop()
        return 0
    except Exception as error:
        (LOG_DIR / "qa_control_launcher.log").write_text(str(error), encoding="utf-8")
        messagebox.showerror("품질검사 관리 시작 실패", str(error))
        return 1
    finally:
        instance.release()


if __name__ == "__main__":
    raise SystemExit(main())
