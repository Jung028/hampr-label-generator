@echo off
REM Double-click to start the Hampr Label Generator and open it in a browser.
REM Leave this window open while you work; closing it stops the server.

cd /d "%~dp0"

set "URL=http://127.0.0.1:5000/"

REM Pick whichever venv exists (.venv or .venv-1), else fall back to python on PATH.
set "PY=python"
if exist ".venv\Scripts\python.exe"   set "PY=.venv\Scripts\python.exe"
if exist ".venv-1\Scripts\python.exe" set "PY=.venv-1\Scripts\python.exe"

echo Starting label generator with %PY% ...
start "" /min "%PY%" web\app.py

REM Give the server a moment to come up, then open the browser.
timeout /t 3 /nobreak >nul
start "" "%URL%"

echo.
echo If the page did not open, browse to %URL% manually.
echo Close this window to stop the server.
echo.
pause
