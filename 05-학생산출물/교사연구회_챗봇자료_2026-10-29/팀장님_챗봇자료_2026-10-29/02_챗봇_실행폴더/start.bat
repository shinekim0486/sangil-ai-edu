rem 0) runtime.zip 자동 압축해제
if not exist "%~dp0runtime\python.exe" (
  if exist "%~dp0runtime.zip" (
    echo [안내] 최초 실행을 위해 runtime.zip 압축을 해제합니다...
    powershell -Command "Expand-Archive -Path '%~dp0runtime.zip' -DestinationPath '%~dp0runtime' -Force"
  )
)
@echo off
chcp 65001 > nul < nul
rem start.bat - 교사연구회 챗봇 서버 실행. 학교 PC 에서 이 파일을 더블클릭하면 된다.
rem Python 설치도, pip 도 필요 없다. 압축본에 든 runtime\python.exe 로 바로 실행한다.
rem 인터넷은 필요하다 — 답을 만드는 OpenAI 호출 때문이다. 학생 PC 는 같은 망(와이파이·유선)에 있으면 된다.
cd /d "%~dp0"
title 교사연구회 챗봇 서버

echo ===============================================
echo  교사연구회 챗봇 서버를 시작합니다.
echo  종료하려면 이 창에서 Ctrl+C 를 누르세요.
echo  (창을 닫아도 꺼집니다. 수업 중에는 닫지 마세요)
echo ===============================================
echo.

rem 1) 파이썬 찾기 — 압축본의 runtime 을 먼저, 없으면 PC 에 설치된 python
set "PY=%~dp0runtime\python.exe"
if exist "%PY%" goto :found
where python >nul 2>&1
if errorlevel 1 (
  echo [문제] runtime\python.exe 를 찾지 못했습니다.
  echo        압축본의 runtime 폴더가 같이 풀렸는지 확인하세요. ^(runtime\python.exe^)
  echo        start.bat 과 app.py 와 runtime 폴더가 같은 곳에 보여야 합니다.
  echo.
  pause
  exit /b 1
)
set "PY=python"
echo [알림] runtime 폴더가 없어 PC 에 설치된 python 을 씁니다.
:found
"%PY%" -c "import sys;print(sys.version.split()[0])" > "%TEMP%\chatbot_pyver.txt" 2>nul
set /p PYVER=<"%TEMP%\chatbot_pyver.txt"
echo 사용할 Python : %PY% ^(%PYVER%^)

rem 2) 필요한 꾸러미가 있는지
"%PY%" -c "import flask, openai, dotenv" >nul 2>&1
if errorlevel 1 (
  echo.
  echo [문제] 필요한 꾸러미^(flask, openai^)가 없습니다.
  echo        runtime 폴더가 통째로 풀리지 않았거나 다른 폴더입니다.
  echo        PC 의 python 을 쓰는 경우라면 이 창에서 다음을 한 번 실행하세요.
  echo          python -m pip install flask openai python-dotenv
  echo.
  pause
  exit /b 1
)

rem 3) 설정 파일(.env)이 없으면 물어보고 만든다. (처음 한 번만)
if not exist ".env" (
  "%PY%" scripts\setup_env.py
  if errorlevel 1 (
    echo.
    echo [중단] 설정을 만들지 못해 서버를 시작하지 않습니다.
    pause
    exit /b 1
  )
)

rem 4) 서버 실행. 학생 접속 주소가 이 창에 나온다.
set "FLASK_DEBUG=0"
if not defined PORT set "PORT=5000"
echo.
"%PY%" app.py

echo.
echo 서버가 종료되었습니다. 위 메시지를 확인하세요.
echo 오류가 보이면 학교PC_실행방법.txt 의 7번 "오류 메시지별 대처" 를 보세요.
pause
