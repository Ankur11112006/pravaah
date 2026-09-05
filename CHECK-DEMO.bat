@echo off
REM Run this the morning of, before anything else. Nine seconds, no internet.
title PRAVAAH self-check
cd /d "%~dp0"
.venv\Scripts\python.exe demo.py
echo.
pause
