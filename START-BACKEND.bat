@echo off
title PRAVAAH backend
cd /d D:\claude\pravaah
echo Starting PRAVAAH backend on port 8010
echo Log: D:\claude\pravaah\out\_api.log
echo Close this window to stop it.
:loop
echo [%date% %time%] starting >> out\_api.log
.venv\Scripts\python.exe -m uvicorn api:app --host 0.0.0.0 --port 8010 >> out\_api.log 2>&1
echo [%date% %time%] exited, restarting in 5 seconds >> out\_api.log
timeout /t 5 /nobreak >nul
goto loop
