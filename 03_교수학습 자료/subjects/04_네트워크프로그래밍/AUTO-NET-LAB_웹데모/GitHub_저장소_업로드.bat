@echo off
chcp 65001 > nul
echo =====================================================================
echo  AUTO-NET LAB GitHub 저장소 원클릭 업로드 스크립트
echo  대상: https://github.com/shinekim0486/AUTO-NET-LAB
echo =====================================================================
echo.
echo 1. Git 저장소 초기화 중...
git init
git config user.name "shinekim0486" 2>nul
git config user.email "shinekim0486@example.com" 2>nul
git add .
git commit -m "Release: AUTO-NET-LAB 네트워크프로그래밍 실습 웹 시뮬레이터 배포"

echo.
echo 2. 메인 브랜치 설정 및 원격 저장소 연결...
git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/shinekim0486/AUTO-NET-LAB.git

echo.
echo 3. GitHub 원격 저장소로 업로드(Push) 진행 중...
echo (GitHub 로그인을 요청하는 브라우저 창이나 토큰 입력창이 뜰 수 있습니다)
git push -u origin main

echo.
echo =====================================================================
echo  업로드가 완료되었습니다!
echo  저장소 확인: https://github.com/shinekim0486/AUTO-NET-LAB
echo =====================================================================
pause