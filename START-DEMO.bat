@echo off
REM PRAVAAH demo. One process serves the officer page AND the API the phone uses,
REM so there is one thing to start and no address to type on stage.
title PRAVAAH backend
cd /d "%~dp0"

echo Starting PRAVAAH on http://localhost:8010
echo.
echo   officer app   http://localhost:8010
echo   the phone     talks to this same port over 10.0.2.2:8010
echo.
echo Leave this window OPEN for the whole demo. Ctrl+C to stop.
echo.

REM Give the server a moment before the browser asks for the page.
start "" /b cmd /c "timeout /t 4 >nul & start http://localhost:8010"

.venv\Scripts\python.exe -m uvicorn api:app --host 0.0.0.0 --port 8010
pause
