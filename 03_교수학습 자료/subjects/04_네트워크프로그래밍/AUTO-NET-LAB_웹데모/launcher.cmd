@echo off
setlocal
set "APPDIR=%~dp0"
set "USERDIR=%LOCALAPPDATA%\AUTO-NET-LAB"
if not exist "%USERDIR%\data" mkdir "%USERDIR%\data"

if not "%AUTO_NET_TEST%"=="1" (
  start "" /b cmd /c "timeout /t 2 /nobreak ^>nul ^& start "" "http://localhost:3000""
)

"%APPDIR%node.exe" "%APPDIR%server.mjs"
endlocal
