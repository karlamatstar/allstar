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
    ("검증 테스트", [PY, "-u", "tools/scripts/run_validation_tests.py"], True),
    ("서버 연결 성능 종합 시험 (API)", [PY, "-u", "tools/scripts/run_performance_tests.py"], True),
    ("서버 연결 끊김 방어 시험 (API)", [PY, "-u", "tools/scripts/run_api_disconnect_test.py"], True),
]

PROFILE_LABELS = {
    "A": "답변 생성: OpenAI / gpt-5.6-luna / 추론 끔(none)\n독립 품질 평가(Judge): Anthropic / claude-sonnet-5 / 낮음(low)",
    "B": "답변 생성: Anthropic / claude-sonnet-4-6 / 낮음(low)\n독립 품질 평가(Judge): OpenAI / gpt-5.6-terra / 낮음(low)",
    "C": "답변 생성: OpenAI / gpt-5.6-luna / 추론 끔(none)\n독립 품질 평가(Judge): OpenAI / gpt-5.6-terra / 낮음(low)",
    "D": "답변 생성: Anthropic / claude-sonnet-4-6 / 낮음(low)\n독립 품질 평가(Judge): Anthropic / claude-sonnet-5 / 낮음(low)",
}


class TestTab(tk.Frame):
    def __init__(self, parent, title: str, command: list[str], confirm: bool = False, detail: str = ""):
        super().__init__(parent, bg="#202634")
        self.command = command
        self.confirm = confirm
        self.process: subprocess.Popen | None = None
        tk.Label(self, text=title, bg="#202634", fg="#e5ebf5",
                 font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=12, pady=(12, 4))
        tk.Label(self, text=detail or "실행 결과는 아래 콘솔과 보고서 폴더에 저장됩니다.",
                 bg="#202634", fg="#9aa9bf", justify="left", font=("Malgun Gothic", 9)).pack(anchor="w", padx=12)
        bar = tk.Frame(self, bg="#202634")
        bar.pack(fill="x", padx=12, pady=9)
        tk.Button(bar, text="실행", command=self.start, bg="#26734d", fg="white", relief="flat", padx=15).pack(side="left")
        tk.Button(bar, text="중지", command=self.stop, bg="#8a3142", fg="white", relief="flat", padx=15).pack(side="left", padx=6)
        tk.Button(bar, text="보고서 폴더", command=self.open_reports, bg="#3b4a63", fg="white", relief="flat", padx=15).pack(side="left")
        self.console = tk.Text(self, bg="#0f131c", fg="#d8e1ef", font=("Consolas", 9), wrap="word")
        self.console.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def start(self):
        if self.process and self.process.poll() is None:
            messagebox.showinfo("실행 중", "이미 테스트가 실행 중입니다.")
            return
        if self.confirm:
            message = (
                "대상: http://localhost:8000\n"
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
        self.process = subprocess.Popen(
            self.command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
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

    def open_reports(self):
        path = ROOT / "_OUTPUT" / "reports"
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)


class QAControl(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AllStar 품질검사 관리")
        self.geometry("1320x800")
        self.minsize(1050, 650)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background="#151923")
        style.configure("TNotebook.Tab", font=("Malgun Gothic", 9, "bold"), padding=(12, 7))
        top = ttk.Notebook(self)
        top.pack(fill="both", expand=True)
        ai = tk.Frame(top, bg="#202634")
        voc = tk.Frame(top, bg="#202634")
        top.add(ai, text="AI 상담 품질검사 (AI Agent QA)")
        top.add(voc, text="고객 의견 분석 품질검사 (VOC QA)")

        ai_tabs = ttk.Notebook(ai)
        ai_tabs.pack(fill="both", expand=True, padx=8, pady=8)
        for title, command, confirm in AI_TESTS:
            ai_tabs.add(TestTab(ai_tabs, title, command, confirm), text=title)

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
        ), text="전체 비AI pytest")
        voc_tabs.add(TestTab(voc_tabs, "단위 테스트", [PY, "-u", "-m", "pytest", "tests/voc/evaluation/test_agent_unit.py", "tests/voc/evaluation/test_llm_judge.py", "-v"]), text="단위 테스트")
        for profile_id in "ABCD":
            command = [PY, "-u", "tools/scripts/run_voc_profile.py", "--profile", profile_id]
            detail = PROFILE_LABELS[profile_id] + "\n대표 사례 2건만 실행합니다. 확장 사고 기능: 사용 안 함(thinking=disabled)"
            voc_tabs.add(TestTab(voc_tabs, f"{profile_id} 테스트", command, True, detail), text=f"{profile_id} 테스트")


if __name__ == "__main__":
    try:
        QAControl().mainloop()
    except Exception as error:
        (LOG_DIR / "qa_control_launcher.log").write_text(str(error), encoding="utf-8")
        messagebox.showerror("품질검사 관리 시작 실패", str(error))
