@echo off
chcp 65001 > nul < nul
rem 백업.bat - 학생 대화 기록(data.db)과 올린 파일(uploads)을 backup 폴더에 날짜를 붙여 복사한다.
rem 서버가 켜져 있어도 된다. 매주 한 번, 그리고 새 압축본으로 바꾸기 전에 꼭 실행한다.
cd /d "%~dp0"
title 챗봇 기록 백업

for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd_HHmm'"`) do set "STAMP=%%T"
set "DEST=backup\%STAMP%"
if not exist "data.db" (
  echo [알림] data.db 가 없습니다. 아직 대화가 한 번도 없었던 것입니다.
  pause
  exit /b 0
)
mkdir "%DEST%" >nul 2>&1
copy /y "data.db" "%DEST%\data.db" >nul
if errorlevel 1 (
  echo [문제] data.db 를 복사하지 못했습니다.
  pause
  exit /b 1
)
if exist "uploads\" xcopy /e /i /q /y "uploads" "%DEST%\uploads" >nul
if exist ".env" copy /y ".env" "%DEST%\.env" >nul

echo 백업 완료 : %DEST%
echo   data.db ^(대화 기록^) · uploads ^(학생이 올린 파일^) · .env ^(설정^)
echo.
echo 이 폴더를 USB 나 드라이브에 옮겨 두면 PC 가 고장 나도 기록이 남습니다.
echo.
pause
