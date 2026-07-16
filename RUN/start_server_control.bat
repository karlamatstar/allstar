@echo off
set "ROOT=%~dp0.."
if exist "%ROOT%\.venv\Scripts\pythonw.exe" (
  start "" "%ROOT%\.venv\Scripts\pythonw.exe" "%~dp0server_control_gui.py"
) else (
  start "" pythonw "%~dp0server_control_gui.py"
)
