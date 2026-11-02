import pandas as pd
from pathlib import Path

# 원본 파일 (복사된 엑셀)
src_path = Path(r"C:\\Users\\AISW\\Desktop\\최종제출\\05-학생산출물\\교사연구회_챗봇자료_2026-10-29\\팀장님_챗봇자료_2026-10-29\\media_1793335879569_cf5f1737.xlsx")
clean_path = src_path.parent / "cleaned_media_1793335879569_cf5f1737.xlsx"

if not src_path.exists():
    raise FileNotFoundError(f"Source file not found: {src_path}")

# Load data
df = pd.read_excel(src_path)

# 결측값 채우기: 숫자형 → 0, 비숫자형 → "N/A"
for col in df.columns:
    if pd.api.types.is_numeric_dtype(df[col]):
        df[col] = df[col].fillna(0)
    else:
        df[col] = df[col].fillna("N/A")

# 중복 행 제거
df_clean = df.drop_duplicates().reset_index(drop=True)

# 저장
df_clean.to_excel(clean_path, index=False)

print("=== Cleaning completed ===")
print(f"Original rows: {df.shape[0]}, after cleaning: {df_clean.shape[0]}")
print(f"Cleaned file saved to: {clean_path}")