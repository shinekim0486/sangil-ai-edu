import shutil
from pathlib import Path

# 최신 엑셀 파일 (원본)
src = Path(r"C:\Users\AISW\.gemini\antigravity\brain\f347975a-626c-43c9-938c-94ace31e494c\.user_uploaded\media_1793335879569_cf5f1737.xlsx")

# 교체 대상 폴더 (전체 교과 파일 포함)
target_root = Path(r"C:\Users\AISW\Desktop\최종제출\05-학생산출물\교사연구회_챗봇자료_2026-10-29\팀장님_챗봇자료_2026-10-29")

if not src.exists():
    raise FileNotFoundError(f"원본 파일이 존재하지 않습니다: {src}")

count = 0
for dst in target_root.rglob("*.xlsx"):
    # 원본 파일과 동일 경로는 건너뜀
    if dst.resolve() == src.resolve():
        continue
    shutil.copy2(src, dst)
    count += 1
    print(f"교체 완료: {dst}")

print(f"\n총 {count}개의 파일을 최신 파일로 교체했습니다.")