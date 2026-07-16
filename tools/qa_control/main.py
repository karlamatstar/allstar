from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
PY = str(PYTHON if PYTHON.exists() else sys.executable)
LOG_DIR = ROOT / "_OUTPUT" / "logs" / "services" / "launcher"
LOG_DIR.mkdir(parents=True, exist_ok=True)

AI_TESTS = [
    ("기본 동작 시험 (Smoke Test)", ["k6", "run", "ops/performance/smoke_test.js"], False),
    ("일반 부하 시험 (Load Test)", ["k6", "run", "ops/performance/load_test.js"], True),
    ("무작위 요청 시험 (Random Test)", ["k6", "run", "ops/performance/random_test.js"], True),
    ("한계 부하 시험 (Stress Test)", ["k6", "run", "ops/performance/stress_test.js"], True),
    ("순간 급증 시험 (Spike Test)", ["k6", "run", "ops/performance/spike_test.js"], True),
    ("장애·기능 검증 시험 (Validation Test)", [PY, "-u", "tools/scripts/run_validation_tests.py"], True),
    ("서버 연결 성능 종합 시험 (API)", [PY, "-u", "tools/scripts/run_performance_tests.py"], True),
    ("서버 연결 끊김 방어 시험 (API)", [PY, "-u", "tools/scripts/run_api_disconnect_test.py"], True),
]

LOAD_SETTINGS = {
    "일반 부하 시험 (Load Test)": ("20", "60"),
    "무작위 요청 시험 (Random Test)": ("100", "60"),
    "한계 부하 시험 (Stress Test)": ("100", "120"),
    "순간 급증 시험 (Spike Test)": ("200", "60"),
}

TEST_DESCRIPTIONS = {
    "기본 동작 시험 (Smoke Test)": (
        "가상 사용자 1명이 서버 상태와 모의 채팅을 각각 한 번 호출하는 가장 가벼운 시험입니다.\n"
        "서버가 켜져 있는지, 기본 연결과 HTTP 200 응답이 정상인지 빠르게 확인할 수 있습니다. 시험이 끝나면 결과가 자동 정리됩니다."
    ),
    "일반 부하 시험 (Load Test)": (
        "설정한 가상 인원이 일정 시간 동안 모의 채팅 요청을 계속 보내는 일상 부하 시험입니다.\n"
        "지속적인 요청에서 응답 지연, 실패율, 처리 안정성이 기준을 유지하는지 확인합니다. 시험이 끝나면 결과가 자동 정리됩니다."
    ),
    "무작위 요청 시험 (Random Test)": (
        "가상 인원 수를 1초마다 1명부터 설정한 최댓값 사이에서 무작위로 바꾸는 변동 부하 시험입니다.\n"
        "예측하기 어려운 요청 증감에서 서버가 안정적으로 응답하는지 확인합니다. 시험이 끝나면 결과가 자동 정리됩니다."
    ),
    "한계 부하 시험 (Stress Test)": (
        "가상 인원을 단계적으로 늘려 최댓값을 유지한 뒤 다시 낮추는 한계 부하 시험입니다.\n"
        "서버의 처리 한계, 고부하 구간의 오류, 부하 감소 후 회복 여부를 확인합니다. 시험이 끝나면 결과가 자동 정리됩니다."
    ),
    "순간 급증 시험 (Spike Test)": (
        "가상 인원을 짧은 시간에 최댓값까지 급격히 올렸다가 다시 낮추는 순간 폭주 시험입니다.\n"
        "갑작스러운 트래픽 급증을 견디는지와 급증 종료 후 정상 상태로 복구되는지 확인합니다. 시험이 끝나면 결과가 자동 정리됩니다."
    ),
    "장애·기능 검증 시험 (Validation Test)": (
        "지연·서버 오류·시간 초과 같은 장애 상황을 k6로 재현하고 전체 기능 검사를 함께 수행합니다.\n"
        "장애 대응과 기존 기능의 정상 동작을 한 번에 확인하며, 완료 후 결함 보고서가 자동 생성됩니다."
    ),
    "서버 연결 성능 종합 시험 (API)": (
        "여러 대표 질문을 서버 연결 통로(API)로 전송해 응답시간, 실패율, 검사 통과율을 종합 측정합니다.\n"
        "질문별 성능 차이와 전체 지연 분포를 확인할 수 있으며, 완료 후 성능 보고서가 자동 생성됩니다."
    ),
    "서버 연결 끊김 방어 시험 (API)": (
        "외부 연결 실패 상황을 의도적으로 발생시켜 재시도와 안전한 대체 응답이 동작하는지 확인합니다.\n"
        "연결 장애가 발생해도 서버가 중단되지 않고 사용자에게 이해하기 쉬운 안내를 반환하는지 검증합니다. 시험 결과는 자동 정리됩니다."
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
    "동일한 대표 사례 2건을 선택한 A~D 모델 조합으로 실행해 답변 생성과 독립 품질 평가를 함께 확인합니다.\n"
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


class TestTab(tk.Frame):
    def __init__(
        self,
        parent,
        title: str,
        command: list[str],
        confirm: bool = False,
        detail: str = "",
        load_settings: tuple[str, str] | None = None,
    ):
        super().__init__(parent, bg="#202634")
        self.command = command
        self.confirm = confirm
        self.process: subprocess.Popen | None = None
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
        tk.Button(bar, text="실행", command=self.start, bg="#26734d", fg="white", relief="flat", padx=15).pack(side="left")
        tk.Button(bar, text="중지", command=self.stop, bg="#8a3142", fg="white", relief="flat", padx=15).pack(side="left", padx=6)
        self.console = tk.Text(self, bg="#0f131c", fg="#d8e1ef", font=("Consolas", 9), wrap="word")
        self.console.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def start(self):
        if self.process and self.process.poll() is None:
            messagebox.showinfo("실행 중", "이미 테스트가 실행 중입니다.")
            return
        env = os.environ.copy()
        load_summary = ""
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
        if self.confirm:
            message = (
                f"대상: http://localhost:8000\n{load_summary}"
                "부하·장애 또는 실제 AI 호출이 포함될 수 있습니다.\n"
                "다른 파괴적 테스트가 실행 중이지 않은지 확인했습니까?"
            )
            if "run_voc_profile.py" in " ".join(self.command):
                message = (
                    "실험군: " + self.command[-1] + "\n"
                    "대표 케이스: TC-01, TC-02\n"
                    "예상 외부 AI 호출: 케이스당 최대 7회, 총 최대 14회\n"
                    "실제 외부 AI 연결 시험(API)을 실행할까요?"
                )
            if not messagebox.askyesno("실행 전 확인", message):
                return
        self.console.insert("end", "\n> " + " ".join(self.command) + "\n")
        if load_summary:
            self.console.insert("end", load_summary)
        self.process = subprocess.Popen(
            self.command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        assert self.process and self.process.stdout
        for line in self.process.stdout:
            self.after(0, self._append, line)
        code = self.process.wait()
        self.after(0, self._append, f"\n[종료 코드: {code}]\n")

    def _append(self, text: str):
        self.console.insert("end", text)
        self.console.see("end")

    def stop(self):
        if self.process and self.process.poll() is None:
            subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, check=False)

class QAControl(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AllStar 품질검사 관리")
        self.geometry("1320x800")
        self.minsize(1050, 650)
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
            ai_tabs.add(
                TestTab(
                    ai_tabs,
                    title,
                    command,
                    confirm,
                    detail=TEST_DESCRIPTIONS[title],
                    load_settings=LOAD_SETTINGS.get(title),
                ),
                text=two_line_tab_label(title),
            )

        voc_tabs = ttk.Notebook(voc)
        voc_tabs.pack(fill="both", expand=True, padx=8, pady=8)
        voc_tabs.add(TestTab(
            voc_tabs,
            "전체 비AI pytest",
            [
                PY, "-u", "-m", "pytest", "tests/voc/evaluation", "-v",
                "--ignore=tests/voc/evaluation/test_pipeline_e2e.py",
                "-k", "not end_to_end",
            ],
            detail=VOC_NON_AI_DESCRIPTION,
        ), text="전체 비AI 검사\n(pytest)")
        voc_tabs.add(TestTab(
            voc_tabs,
            "단위 테스트",
            [PY, "-u", "-m", "pytest", "tests/voc/evaluation/test_agent_unit.py", "tests/voc/evaluation/test_llm_judge.py", "-v"],
            detail=VOC_UNIT_DESCRIPTION,
        ), text="단위 테스트\n(Unit Test)")
        for profile_id in "ABCD":
            command = [PY, "-u", "tools/scripts/run_voc_profile.py", "--profile", profile_id]
            detail = (
                VOC_PROFILE_DESCRIPTION
                + "\n\n"
                + PROFILE_LABELS[profile_id]
                + "\n대표 사례 2건만 실행합니다. 확장 사고 기능: 사용 안 함(thinking=disabled)"
            )
            title = f"에이전트 교차 테스트 ({profile_id})"
            voc_tabs.add(TestTab(voc_tabs, title, command, True, detail), text=f"에이전트 교차 테스트\n({profile_id})")


if __name__ == "__main__":
    try:
        QAControl().mainloop()
    except Exception as error:
        (LOG_DIR / "qa_control_launcher.log").write_text(str(error), encoding="utf-8")
        messagebox.showerror("품질검사 관리 시작 실패", str(error))
