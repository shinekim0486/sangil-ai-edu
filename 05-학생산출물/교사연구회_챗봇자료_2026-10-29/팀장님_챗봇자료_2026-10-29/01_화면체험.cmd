@echo off
chcp 65001 >nul
cd /d "%~dp002_챗봇_실행폴더"
set "PYTHONIOENCODING=utf-8"
"%~dp002_챗봇_실행폴더\runtime\python.exe" -X utf8 scripts\demo_mode.py
if errorlevel 1 pause
