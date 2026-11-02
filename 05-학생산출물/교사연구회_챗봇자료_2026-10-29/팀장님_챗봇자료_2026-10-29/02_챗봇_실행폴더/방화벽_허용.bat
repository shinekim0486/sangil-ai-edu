@echo off
chcp 65001 > nul < nul
rem 방화벽_허용.bat - 학생 PC 가 이 서버(포트 5000)에 들어올 수 있게 Windows 방화벽 규칙을 넣는다.
rem 처음 start.bat 을 켤 때 뜨는 방화벽 창에서 "액세스 허용" 을 눌렀다면 이 파일은 필요 없다.
rem 관리자 권한이 필요해서 더블클릭하면 권한 요청 창(UAC)이 뜬다. "예" 를 누르면 된다.
cd /d "%~dp0"
set "RULENAME=teacher-research-agent"
set "PORT=5000"

net session >nul 2>&1
if errorlevel 1 (
  echo 관리자 권한을 요청합니다. 창이 뜨면 "예" 를 누르세요.
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  if errorlevel 1 (
    echo.
    echo [문제] 관리자 권한을 얻지 못했습니다.
    echo        이 파일을 마우스 오른쪽 클릭 - "관리자 권한으로 실행" 으로 다시 여세요.
    pause
  )
  exit /b
)

echo 방화벽 규칙 "%RULENAME%" ^(TCP %PORT% 들어오는 연결 허용^) 을 넣습니다.
netsh advfirewall firewall delete rule name="%RULENAME%" >nul 2>&1
netsh advfirewall firewall add rule name="%RULENAME%" dir=in action=allow protocol=TCP localport=%PORT% profile=private,domain,public
if errorlevel 1 (
  echo.
  echo [문제] 규칙을 넣지 못했습니다. 위 메시지를 확인하세요.
) else (
  echo.
  echo 완료. 학생 PC 에서 http://서버주소:%PORT% 로 접속되는지 확인하세요.
  echo 포트를 바꿨다면 이 파일 위쪽의 PORT 도 같이 바꾸세요.
)
echo.
pause
