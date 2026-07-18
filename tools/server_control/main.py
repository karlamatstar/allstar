from __future__ import annotations

import json
import os
import queue
import socket
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from allstar.shared.single_instance import DUPLICATE_INSTANCE_EXIT_CODE, SingleInstanceLock
from lifecycle import (
    docker_ready,
    ensure_docker_ready,
    listening_pids,
    running_non_project_containers,
    stop_docker_desktop,
    stop_project_and_docker,
    stop_project_services,
    is_allstar_host_streamlit,
    terminate_streamlit_processes,
)


SRC_ROOT = ROOT / "src"
PYTHONW = ROOT / ".venv" / "Scripts" / "pythonw.exe"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
LOG_DIR = ROOT / "_OUTPUT" / "logs" / "services"
LOG_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DIR = LOG_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
SHUTDOWN_LOG = LOG_DIR / "shutdown_guard.log"
DEFAULT_WINDOW_SIZE = (1440, 900)
MINIMUM_WINDOW_SIZE = (1200, 820)
LEFT_PANEL_WIDTH = 440

SERVICES = [
    ("컨테이너 실행 환경 (Docker Desktop)", "docker-desktop", None, None, "system"),
    ("AI 상담 서버 (Portfolio API)", "portfolio-api", 8000, "http://localhost:8000/docs", "docker"),
    ("부하 시험 실행기 (K6 Runner)", "k6-runner", 8200, "http://localhost:8200/docs", "docker"),
    ("통합 화면 (Streamlit)", "streamlit", 8501, "http://localhost:8501", "docker"),
    ("고객 의견 분석 서버 (VOC API)", "voc-api", 8100, "http://localhost:8100/docs", "docker"),
    ("질문 의도 분석 (Interpreter)", "voc-interpreter", 6001, None, "docker"),
    ("관련 의견 검색 (Retriever)", "voc-retriever", 6002, None, "docker"),
    ("내용 요약 (Summarizer)", "voc-summarizer", 6003, None, "docker"),
    ("초기 품질 평가 (Evaluator)", "voc-evaluator", 6004, None, "docker"),
    ("결과 검토 (Critic)", "voc-critic", 6005, None, "docker"),
    ("최종 답변 개선 (Improver)", "voc-improver", 6006, None, "docker"),
    ("상태 정보 수집 (Prometheus)", "prometheus", 9090, "http://localhost:9090", "docker"),
    ("운영 상태 화면 (Grafana)", "grafana", 3000, "http://localhost:3000", "docker"),
]

WEB_LINKS = [
    ("AI 상담 서버 기능 명세", "portfolio-api", 8000, "http://localhost:8000/docs"),
    ("고객 의견 분석 서버 기능 명세", "voc-api", 8100, "http://localhost:8100/docs"),
    ("통합 대시보드", "streamlit", 8501, "http://localhost:8501"),
    ("상태 정보 수집 (Prometheus)", "prometheus", 9090, "http://localhost:9090"),
    ("운영 상태 화면 (Grafana)", "grafana", 3000, "http://localhost:3000"),
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
        self.title("AllStar 서버 관리")
        self._configure_window()
        self.configure(bg="#151923")
        self.streamlit_process: subprocess.Popen | None = None
        self.streamlit_log = None
        self.closing = False
        self.operation_running = False
        self.status_refresh_running = False
        self.status_after_id: str | None = None
        self.events: queue.Queue[str] = queue.Queue()
        self.rows: dict[str, tk.Label] = {}
        self.web_buttons: dict[str, tuple[tk.Button, str]] = {}
        self.service_status: dict[str, bool] = {}
        self.action_buttons: list[tk.Button] = []
        self.selected = tk.StringVar(value="portfolio-api")
        self.state_path = Path(
            os.getenv("ALLSTAR_SERVER_STATE", RUNTIME_DIR / f"server_control_{os.getpid()}.json")
        )
        self.clean_marker = Path(
            os.getenv("ALLSTAR_SERVER_CLEAN_MARKER", RUNTIME_DIR / f"server_control_{os.getpid()}.clean")
        )
        self._write_runtime_state()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close_application)
        self.after(300, self._request_status_refresh)
        self.after(200, self._drain_events)

    def _configure_window(self):
        width, height = DEFAULT_WINDOW_SIZE
        minimum_width, minimum_height = MINIMUM_WINDOW_SIZE
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(minimum_width, minimum_height)

    def _button(self, parent, text, command, color="#2f3b52"):
        return tk.Button(
            parent, text=text, command=command, bg=color, fg="white",
            activebackground="#496080", activeforeground="white",
            relief="flat", padx=13, pady=7, font=("Malgun Gothic", 9, "bold"),
        )

    def _build(self):
        top = tk.Frame(self, bg="#151923")
        top.pack(fill="x", padx=14, pady=12)
        tk.Label(top, text="⭐ AllStar 서버 관리 (Server Control Center)", bg="#151923", fg="#d9e7ff",
                 font=("Malgun Gothic", 15, "bold")).pack(side="left")
        actions = tk.Frame(top, bg="#151923")
        actions.pack(side="right")
        action_specs = [
            ("상태 새로고침", self._request_status_refresh, "#2f3b52"),
            ("전체 시작", self.start_all, "#26734d"),
            ("서버 전체 종료", self.stop_all, "#8a3142"),
            ("Docker 포함 전체 종료", self.stop_all_with_docker, "#a32626"),
        ]
        for label, command, color in action_specs:
            button = self._button(actions, label, command, color)
            button.pack(side="left", padx=4)
            self.action_buttons.append(button)

        body = tk.PanedWindow(self, orient="horizontal", sashwidth=6, bg="#151923")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        left = tk.Frame(body, bg="#202634", width=LEFT_PANEL_WIDTH)
        right = tk.Frame(body, bg="#202634")
        body.add(left, minsize=420)
        body.add(right, minsize=700)

        tk.Label(left, text="실행 서비스", bg="#202634", fg="#a9b8d0",
                 font=("Malgun Gothic", 10, "bold")).pack(anchor="w", padx=12, pady=10)
        for name, key, port, _, _ in SERVICES:
            frame = tk.Frame(left, bg="#202634")
            frame.pack(fill="x", padx=10, pady=2)
            tk.Radiobutton(
                frame, text=f"{name}{f'  :{port}' if port else ''}", variable=self.selected, value=key,
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

        tk.Label(left, text="웹 화면 바로가기", bg="#202634", fg="#a9b8d0",
                 font=("Malgun Gothic", 10, "bold")).pack(anchor="w", padx=12, pady=(4, 6))
        web_links = tk.Frame(left, bg="#202634")
        web_links.pack(fill="x", padx=10, pady=(0, 12))
        for label, key, _, url in WEB_LINKS:
            button = self._button(
                web_links,
                f"⚪ {label}",
                lambda service_key=key: self.open_web_service(service_key),
            )
            button.pack(fill="x", pady=2)
            self.web_buttons[key] = (button, label)

        tk.Label(right, text="선택 서비스 실행 기록 (Log)", bg="#202634", fg="#a9b8d0",
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

    def _write_runtime_state(self, streamlit_pid: int | None = None):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(
                {"gui_pid": os.getpid(), "streamlit_pid": streamlit_pid},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _start_streamlit(self):
        existing_pids = sorted(pid for pid in listening_pids(8501) if is_allstar_host_streamlit(pid))
        if existing_pids:
            self._write_runtime_state(existing_pids[0])
            self.events.put("\n[Streamlit] 8501 포트에서 이미 실행 중입니다.\n")
            return
        if self.streamlit_process and self.streamlit_process.poll() is None:
            return
        if not PYTHON.exists():
            messagebox.showerror("Python 없음", f"가상환경을 찾을 수 없습니다.\n{PYTHON}")
            return
        path = LOG_DIR / "streamlit.log"
        self.streamlit_log = path.open("a", encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(SRC_ROOT), env.get("PYTHONPATH", "")) if part
        )
        self.streamlit_process = subprocess.Popen(
            [str(PYTHON), "-u", "-m", "streamlit", "run", "src/allstar/ui/dashboard/streamlit_app.py",
             "--server.address", "127.0.0.1", "--server.port", "8501", "--server.headless", "true"],
            cwd=ROOT, stdout=self.streamlit_log, stderr=subprocess.STDOUT,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self._write_runtime_state(self.streamlit_process.pid)

    def _stop_streamlit(self):
        pids = {pid for pid in listening_pids(8501) if is_allstar_host_streamlit(pid)}
        if self.streamlit_process and self.streamlit_process.poll() is None:
            pids.add(self.streamlit_process.pid)
        terminate_streamlit_processes(pids, SHUTDOWN_LOG)
        if self.streamlit_log:
            self.streamlit_log.close()
            self.streamlit_log = None
        self.streamlit_process = None
        self._write_runtime_state()

    def start_all(self):
        if self.operation_running:
            self.events.put("\n[안내] 다른 시작·종료 작업이 진행 중입니다.\n")
            return
        self.operation_running = True
        self._set_action_buttons(False)

        def worker():
            self.events.put("\n[전체 시작] Docker Desktop 상태를 확인합니다.\n")
            if not ensure_docker_ready(SHUTDOWN_LOG):
                self.events.put("[실패] Docker Desktop을 준비하지 못했습니다. 종료 기록을 확인하세요.\n")
                self.after(0, self._finish_operation)
                return
            self.events.put("[준비 완료] Docker Desktop이 실행 중입니다. 서버를 시작합니다.\n")
            docker_services = [key for _, key, _, _, kind in SERVICES if kind == "docker"]
            completed = subprocess.run(
                ["docker", "compose", "up", "-d", "--build", *docker_services],
                cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW, check=False,
            )
            self.events.put(completed.stdout or "")
            if completed.returncode != 0:
                self.events.put(f"\n[서버 시작 실패: {completed.returncode}]\n")
            self.after(0, self._finish_operation)

        threading.Thread(target=worker, daemon=True).start()

    def stop_all(self):
        if self.operation_running:
            self.events.put("\n[안내] 다른 시작·종료 작업이 진행 중입니다.\n")
            return
        self.operation_running = True
        self._set_action_buttons(False)

        def worker():
            stop_project_services(ROOT, self.state_path, SHUTDOWN_LOG)
            self.events.put("\n[서버 전체 종료] Streamlit과 프로젝트 서버를 종료했습니다. Docker Desktop은 유지합니다.\n")
            self.after(0, self._finish_operation)

        threading.Thread(target=worker, daemon=True).start()

    def stop_all_with_docker(self):
        if self.operation_running:
            self.events.put("\n[안내] 다른 시작·종료 작업이 진행 중입니다.\n")
            return
        self.operation_running = True
        self._set_action_buttons(False)
        self.events.put("\n[Docker 포함 전체 종료] 다른 프로젝트 컨테이너를 확인합니다.\n")

        def inspect_worker():
            other_containers = running_non_project_containers(ROOT)
            self.after(0, lambda: self._confirm_docker_shutdown(other_containers))

        threading.Thread(target=inspect_worker, daemon=True).start()

    def _confirm_docker_shutdown(self, other_containers: list[str]):
        message = (
            "AllStar 서버와 Docker Desktop을 모두 종료합니다.\n\n"
            "Docker를 사용하는 다른 프로젝트도 영향을 받을 수 있습니다. 계속하시겠습니까?"
        )
        if other_containers:
            preview = ", ".join(other_containers[:5])
            suffix = " 외" if len(other_containers) > 5 else ""
            message += f"\n\nAllStar 이외 실행 중 컨테이너 {len(other_containers)}개: {preview}{suffix}"
        if not messagebox.askyesno("Docker 포함 전체 종료 확인", message, icon="warning"):
            self.events.put("[취소] Docker 포함 전체 종료를 취소했습니다.\n")
            self._finish_operation()
            return

        def worker():
            success = stop_project_and_docker(ROOT, self.state_path, SHUTDOWN_LOG)
            if success:
                self.events.put("[완료] AllStar 서버와 Docker Desktop을 모두 종료했습니다.\n")
            else:
                self.events.put("[일부 실패] 종료 기록에서 실패 원인을 확인하세요.\n")
            self.after(0, self._finish_operation)

        threading.Thread(target=worker, daemon=True).start()

    def _set_action_buttons(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for button in self.action_buttons:
            button.configure(state=state)

    def _finish_operation(self):
        self.operation_running = False
        self._set_action_buttons(True)
        self._request_status_refresh()

    def close_application(self):
        if self.closing:
            return
        self.closing = True
        self._set_action_buttons(False)
        self.title("AllStar 서버 관리 - 서버 전체 종료 중...")
        self.events.put("\n[프로그램 종료 요청] 서버 전체 종료 후 창을 닫습니다. Docker Desktop은 유지합니다.\n")

        if self.streamlit_log:
            self.streamlit_log.close()
            self.streamlit_log = None

        def worker():
            success = stop_project_services(ROOT, self.state_path, SHUTDOWN_LOG)
            if success:
                self.clean_marker.parent.mkdir(parents=True, exist_ok=True)
                self.clean_marker.write_text("clean", encoding="utf-8")
            self.after(0, self.destroy)

        threading.Thread(target=worker, daemon=True).start()

    def start_selected(self):
        _, key, _, _, kind = self._service(self.selected.get())
        if kind == "system":
            threading.Thread(target=self._start_docker_selected, daemon=True).start()
        elif kind == "host":
            self._start_streamlit()
        else:
            if not docker_ready():
                self.events.put(
                    "\n[개별 시작 불가] Docker Desktop이 꺼져 있습니다.\n"
                    "실행 서비스에서 '컨테이너 실행 환경 (Docker Desktop)'을 선택해 먼저 시작하거나 "
                    "상단의 '전체 시작'을 이용하세요.\n"
                )
                return
            self._docker("up", "-d", "--build", key, done=self._request_status_refresh)

    def _start_docker_selected(self):
        success = ensure_docker_ready(SHUTDOWN_LOG)
        self.events.put("\nDocker Desktop 준비 완료\n" if success else "\nDocker Desktop 실행 실패\n")
        self.after(0, self._request_status_refresh)

    def stop_selected(self):
        _, key, _, _, kind = self._service(self.selected.get())
        if kind == "system":
            threading.Thread(target=self._stop_docker_selected, daemon=True).start()
        elif kind == "host":
            threading.Thread(target=self._stop_streamlit_selected, daemon=True).start()
        else:
            self._docker("stop", key, done=self._request_status_refresh)

    def _stop_docker_selected(self):
        success = stop_docker_desktop(SHUTDOWN_LOG)
        self.events.put("\nDocker Desktop 종료 완료\n" if success else "\nDocker Desktop 종료 실패\n")
        self.after(0, self._request_status_refresh)

    def _stop_streamlit_selected(self):
        self._stop_streamlit()
        self.events.put("\nStreamlit 종료 완료\n")
        self.after(0, self._request_status_refresh)

    def open_web_service(self, key: str):
        label, port, url = next((label, port, url) for label, link_key, port, url in WEB_LINKS if link_key == key)
        if not port_open(port):
            messagebox.showwarning(
                "서버 실행 필요",
                f"'{label}'에 접속할 수 없습니다.\n\n해당 서버를 먼저 시작한 뒤 다시 눌러주세요.",
            )
            self._request_status_refresh()
            return
        webbrowser.open(url)

    def load_log(self):
        _, key, _, _, kind = self._service(self.selected.get())
        if kind == "system":
            self._run(["docker", "desktop", "status"])
        elif kind == "host":
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
        if not self.closing:
            self.after(200, self._drain_events)

    def _request_status_refresh(self):
        if self.closing or self.status_refresh_running:
            return
        self.status_refresh_running = True

        def worker():
            results = {"docker-desktop": docker_ready()}
            port_services = [(key, port) for _, key, port, _, _ in SERVICES if port]
            with ThreadPoolExecutor(max_workers=len(port_services)) as executor:
                checks = {key: executor.submit(port_open, port) for key, port in port_services}
                results.update({key: check.result() for key, check in checks.items()})
            self.after(0, self._apply_status, results)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_status(self, results: dict[str, bool]):
        if self.closing:
            return
        for _, key, _, _, _ in SERVICES:
            ready = results.get(key, False)
            self.service_status[key] = ready
            self.rows[key].configure(text="● 실행 중" if ready else "● 중지", fg="#70c987" if ready else "#788398")
            if key in self.web_buttons:
                button, label = self.web_buttons[key]
                button.configure(text=f"{'🟢' if ready else '⚪'} {label}")
        self.status_refresh_running = False
        if self.status_after_id:
            self.after_cancel(self.status_after_id)
        self.status_after_id = self.after(2500, self._scheduled_status_refresh)

    def _scheduled_status_refresh(self):
        self.status_after_id = None
        self._request_status_refresh()


def main() -> int:
    instance = SingleInstanceLock("Local\\AllStarServerControlCenter")
    if not instance.acquire():
        messagebox.showwarning("이미 실행 중입니다", "서버 관리 프로그램이 이미 실행 중입니다.")
        return DUPLICATE_INSTANCE_EXIT_CODE
    try:
        ServerControl().mainloop()
        return 0
    except Exception as error:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (LOG_DIR / "server_control_launcher.log").write_text(str(error), encoding="utf-8")
        messagebox.showerror("서버 관리 시작 실패", str(error))
        return 1
    finally:
        instance.release()


if __name__ == "__main__":
    raise SystemExit(main())
