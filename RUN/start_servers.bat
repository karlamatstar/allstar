@echo off
set "ROOT=%~dp0.."
if exist "%ROOT%\.venv\Scripts\pythonw.exe" (
  start "" "%ROOT%\.venv\Scripts\pythonw.exe" "%ROOT%\tools\server_control\main.py"
) else (
  start "" pythonw "%ROOT%\tools\server_control\main.py"
)
