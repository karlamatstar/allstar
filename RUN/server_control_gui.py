from __future__ import annotations

import queue
import socket
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox


ROOT = Path(__file__).resolve().parent.parent
PYTHONW = ROOT / ".venv" / "Scripts" / "pythonw.exe"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
LOG_DIR = ROOT / "logs" / "services"
LOG_DIR.mkdir(parents=True, exist_ok=True)

SERVICES = [
    ("Portfolio API", "portfolio-api", 8000, "http://localhost:8000/docs", "docker"),
    ("Streamlit", "streamlit", 8501, "http://localhost:8501", "host"),
    ("VOC API", "voc-api", 8100, "http://localhost:8100/docs", "docker"),
    ("Interpreter", "voc-interpreter", 6001, None, "docker"),
    ("Retriever", "voc-retriever", 6002, None, "docker"),
    ("Summarizer", "voc-summarizer", 6003, None, "docker"),
    ("Evaluator", "voc-evaluator", 6004, None, "docker"),
    ("Critic", "voc-critic", 6005, None, "docker"),
    ("Improver", "voc-improver", 6006, None, "docker"),
    ("Prometheus", "prometheus", 9090, "http://localhost:9090", "docker"),
    ("Grafana", "grafana", 3000, "http://localhost:3000", "docker"),
]


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


class ServerControl(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AllStar Server Control Center")
        self.geometry("1280x760")
        self.minsize(1000, 620)
        self.configure(bg="#151923")
        self.streamlit_process: subprocess.Popen | None = None
        self.streamlit_log = None
        self.events: queue.Queue[str] = queue.Queue()
        self.rows: dict[str, tk.Label] = {}
        self.selected = tk.StringVar(value="portfolio-api")
        self._build()
        self.after(300, self._refresh_status)
        self.after(200, self._drain_events)

    def _button(self, parent, text, command, color="#2f3b52"):
        return tk.Button(
            parent, text=text, command=command, bg=color, fg="white",
            activebackground="#496080", activeforeground="white",
            relief="flat", padx=13, pady=7, font=("Malgun Gothic", 9, "bold"),
        )

    def _build(self):
        top = tk.Frame(self, bg="#151923")
        top.pack(fill="x", padx=14, pady=12)
        tk.Label(top, text="⭐ AllStar Server Control Center", bg="#151923", fg="#d9e7ff",
                 font=("Malgun Gothic", 15, "bold")).pack(side="left")
        self._button(top, "전체 시작", self.start_all, "#26734d").pack(side="right", padx=4)
        self._button(top, "전체 종료", self.stop_all, "#8a3142").pack(side="right", padx=4)
        self._button(top, "상태 새로고침", self._refresh_status).pack(side="right", padx=4)

        body = tk.PanedWindow(self, orient="horizontal", sashwidth=6, bg="#151923")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        left = tk.Frame(body, bg="#202634", width=390)
        right = tk.Frame(body, bg="#202634")
        body.add(left, minsize=360)
        body.add(right, minsize=550)

        tk.Label(left, text="서비스", bg="#202634", fg="#a9b8d0",
                 font=("Malgun Gothic", 10, "bold")).pack(anchor="w", padx=12, pady=10)
        for name, key, port, _, _ in SERVICES:
            frame = tk.Frame(left, bg="#202634")
            frame.pack(fill="x", padx=10, pady=2)
            tk.Radiobutton(
                frame, text=f"{name}  :{port}", variable=self.selected, value=key,
                command=self.load_log, bg="#202634", fg="#e5ebf5",
                selectcolor="#2f3b52", activebackground="#202634", activeforeground="white",
                anchor="w", font=("Malgun Gothic", 9),
            ).pack(side="left", fill="x", expand=True)
            status = tk.Label(frame, text="● 확인 중", bg="#202634", fg="#d4a72c",
                              font=("Malgun Gothic", 9, "bold"))
            status.pack(side="right")
            self.rows[key] = status

        controls = tk.Frame(left, bg="#202634")
        controls.pack(fill="x", padx=10, pady=12)
        self._button(controls, "개별 시작", self.start_selected, "#26734d").pack(side="left", padx=3)
        self._button(controls, "개별 종료", self.stop_selected, "#8a3142").pack(side="left", padx=3)
        self._button(controls, "접속", self.open_selected).pack(side="left", padx=3)

        tk.Label(right, text="선택 서비스 로그", bg="#202634", fg="#a9b8d0",
                 font=("Malgun Gothic", 10, "bold")).pack(anchor="w", padx=12, pady=10)
        self.log = tk.Text(right, bg="#0f131c", fg="#d8e1ef", insertbackground="white",
                           font=("Consolas", 9), relief="flat", wrap="word")
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.load_log()

    def _run(self, args: list[str], done=None):
        def worker():
            try:
                completed = subprocess.run(
                    args, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                self.events.put(completed.stdout or "")
                if completed.returncode:
                    self.events.put(f"\n[명령 실패: {completed.returncode}]\n")
            except Exception as error:
                self.events.put(f"\n[실행 오류] {error}\n")
            if done:
                self.after(0, done)
        threading.Thread(target=worker, daemon=True).start()

    def _docker(self, *args: str, done=None):
        self._run(["docker", "compose", *args], done=done)

    def _service(self, key: str):
        return next(item for item in SERVICES if item[1] == key)

    def _start_streamlit(self):
        if self.streamlit_process and self.streamlit_process.poll() is None:
            return
        if not PYTHON.exists():
            messagebox.showerror("Python 없음", f"가상환경을 찾을 수 없습니다.\n{PYTHON}")
            return
        path = LOG_DIR / "streamlit.log"
        self.streamlit_log = path.open("a", encoding="utf-8")
        self.streamlit_process = subprocess.Popen(
            [str(PYTHON), "-u", "-m", "streamlit", "run", "dashboard/streamlit_app.py",
             "--server.address", "127.0.0.1", "--server.port", "8501"],
            cwd=ROOT, stdout=self.streamlit_log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def _stop_streamlit(self):
        if self.streamlit_process and self.streamlit_process.poll() is None:
            self.streamlit_process.terminate()
        if self.streamlit_log:
            self.streamlit_log.close()
            self.streamlit_log = None

    def start_all(self):
        docker_services = [key for _, key, _, _, kind in SERVICES if kind == "docker"]
        self._docker("up", "-d", *docker_services, done=self._start_streamlit)

    def stop_all(self):
        self._stop_streamlit()
        self._docker("stop")

    def start_selected(self):
        _, key, _, _, kind = self._service(self.selected.get())
        self._start_streamlit() if kind == "host" else self._docker("up", "-d", key)

    def stop_selected(self):
        _, key, _, _, kind = self._service(self.selected.get())
        self._stop_streamlit() if kind == "host" else self._docker("stop", key)

    def open_selected(self):
        _, _, _, url, _ = self._service(self.selected.get())
        if url:
            webbrowser.open(url)
        else:
            messagebox.showinfo("접속 주소 없음", "이 서비스는 브라우저 화면을 제공하지 않습니다.")

    def load_log(self):
        _, key, _, _, kind = self._service(self.selected.get())
        if kind == "host":
            path = LOG_DIR / "streamlit.log"
            content = path.read_text(encoding="utf-8", errors="replace")[-30000:] if path.exists() else "아직 로그가 없습니다."
            self._set_log(content)
        else:
            self._run(["docker", "compose", "logs", "--tail", "250", key], done=None)

    def _set_log(self, text: str):
        self.log.delete("1.0", "end")
        self.log.insert("end", text)
        self.log.see("end")

    def _drain_events(self):
        changed = False
        chunks = []
        while True:
            try:
                chunks.append(self.events.get_nowait())
                changed = True
            except queue.Empty:
                break
        if changed:
            self._set_log("".join(chunks))
        self.after(200, self._drain_events)

    def _refresh_status(self):
        for _, key, port, _, _ in SERVICES:
            ready = port_open(port)
            self.rows[key].configure(text="● 실행 중" if ready else "● 중지", fg="#70c987" if ready else "#788398")
        self.after(2500, self._refresh_status)


if __name__ == "__main__":
    try:
        ServerControl().mainloop()
    except Exception as error:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (LOG_DIR / "server_control_launcher.log").write_text(str(error), encoding="utf-8")
        messagebox.showerror("Server Control 시작 실패", str(error))
