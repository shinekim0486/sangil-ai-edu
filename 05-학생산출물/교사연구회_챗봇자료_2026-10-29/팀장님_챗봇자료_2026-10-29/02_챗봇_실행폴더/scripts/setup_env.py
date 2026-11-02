# -*- coding: utf-8 -*-
"""
처음 한 번 — 설정 파일(.env)을 물어보고 만든다. start.bat 이 .env 가 없을 때 부른다.

묻는 것은 세 가지다.
  1. OpenAI API 키       (필수 · 입력하는 동안 화면에 안 보인다)
  2. 팀 코드 목록        (엔터면 CAR1~CAR6)
  3. 수업용 접속 코드    (엔터면 없음)
관리자 열쇠(ADMIN_KEY)는 자동으로 만들어 보여 준다. 기록을 내려받을 때 쓴다.
"""
import getpass
import os
import secrets
import sys

sys.stdout.reconfigure(line_buffering=True)   # 파이프로 볼 때도 바로 찍히게
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = os.path.join(HERE, ".env")


def secret(prompt):
    """키 입력. 콘솔이면 화면에 안 보이게(getpass), 아니면(파이프·다른 프로그램에서 부를 때) 그냥 읽는다."""
    if sys.stdin.isatty():
        try:
            return getpass.getpass(prompt).strip()
        except Exception:
            pass
    return ask(prompt)


def ask(prompt, default=""):
    try:
        v = input(prompt).strip()
    except EOFError:
        v = ""
    return v or default


def main():
    if os.path.exists(ENV):
        print(".env 가 이미 있습니다. 바꾸려면 파일을 메모장으로 열어 고치세요.")
        return 0

    print("=" * 56)
    print("  처음 실행 — 설정 파일(.env)을 만듭니다. 한 번만 합니다.")
    print("=" * 56)
    print()
    print("1) OpenAI API 키를 붙여 넣고 엔터. (sk- 로 시작 · 입력 중 화면에 안 보임)")
    print("   키는 https://platform.openai.com/api-keys 에서 만듭니다.")
    key = ""
    for _ in range(3):
        key = secret("   API 키: ")
        if key.startswith("sk-") and len(key) > 20:
            break
        print("   [다시] sk- 로 시작하는 긴 문자열이어야 합니다. 앞뒤 공백·따옴표 없이 붙여 넣으세요.")
        key = ""
    if not key:
        print()
        print("[중단] API 키가 없으면 챗봇이 '모의 응답'만 냅니다. 키를 준비한 뒤 start.bat 을 다시 실행하세요.")
        return 1

    print()
    print("2) 팀 코드 목록. 학생이 로그인할 때 치는 코드입니다. 쉼표로 구분.")
    teams = ask("   팀 코드 [CAR1,CAR2,CAR3,CAR4,CAR5,CAR6]: ", "CAR1,CAR2,CAR3,CAR4,CAR5,CAR6")
    teams = ",".join(t.strip().upper() for t in teams.split(",") if t.strip())

    print()
    print("3) 수업용 공통 접속 코드. 팀 코드 외에 한 번 더 걸고 싶을 때만. 비우면 없음.")
    access = ask("   접속 코드 [없음]: ", "")

    admin = secrets.token_hex(6)

    lines = [
        "# 교사연구회 챗봇 설정 — start.bat 이 처음 실행될 때 만들었다. 메모장으로 고칠 수 있다.",
        "",
        "# OpenAI API 키. 없으면 모의 응답 모드로 돈다.",
        "OPENAI_API_KEY=" + key,
        "",
        "# 모델 — 단계 판정과 되묻기는 저렴한 모델, 완성 코드 턴만 고급 모델",
        "MODEL_JUDGE=gpt-4o-mini",
        "MODEL_FAST=gpt-4o-mini",
        "MODEL_STD=gpt-4o",
        "MODEL_DEEP=gpt-4o",
        "",
        "# 접속 제한",
        "TEAM_CODES=" + teams,
        "ACCESS_CODE=" + access,
        "",
        "# 기록 내려받기 열쇠 — http://주소:5000/admin/export?key=" + admin,
        "ADMIN_KEY=" + admin,
        "",
        "# 포트를 바꾸려면 (기본 5000)",
        "# PORT=5000",
        "",
    ]
    with open(ENV, "w", encoding="utf-8", newline="\n") as fp:
        fp.write("\n".join(lines))

    print()
    print("저장했습니다: " + ENV)
    print("  팀 코드    : " + teams)
    print("  접속 코드  : " + (access or "없음"))
    print("  관리자 열쇠: " + admin + "   ← 기록 내려받을 때 씁니다. 적어 두세요.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
