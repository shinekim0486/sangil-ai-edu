import pandas as pd
import sys
from pathlib import Path

def main():
    # 새로 업로드된 엑셀 파일 경로 (artifact 위치)
    excel_path = Path(r"C:\Users\AISW\.gemini\antigravity\brain\f347975a-626c-43c9-938c-94ace31e494c\.user_uploaded\media_1793335692470_2dc2844f.xlsx")
    if not excel_path.exists():
        print(f"Error: 파일을 찾을 수 없습니다: {excel_path}")
        sys.exit(1)

    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f"Excel 파일을 읽는 중 오류 발생: {e}")
        sys.exit(1)

    print("=== 데이터 개요 ===")
    print(f"행 수: {df.shape[0]}, 열 수: {df.shape[1]}")
    print("컬럼 목록:")
    for col in df.columns:
        print(f" - {col}")

    print("\n=== 결측값 현황 ===")
    missing = df.isnull().sum()
    for col, cnt in missing.items():
        print(f"{col}: {cnt}")

    print("\n=== 중복 행 수 ===")
    dup_cnt = df.duplicated().sum()
    print(f"중복 행: {dup_cnt}")

    # 숫자형 컬럼 통계
    numeric_cols = df.select_dtypes(include='number').columns
    if len(numeric_cols):
        print("\n=== 숫자형 컬럼 통계 ===")
        print(df[numeric_cols].describe())
    else:
        print("\n숫자형 컬럼이 없습니다.")

    # 문자열 컬럼에서 빈 문자열 확인
    object_cols = df.select_dtypes(include='object').columns
    if len(object_cols):
        print("\n=== 문자열 컬럼 빈 문자열 확인 ===")
        for col in object_cols:
            empty_cnt = (df[col] == "").sum()
            if empty_cnt:
                print(f"{col}: 빈 문자열 {empty_cnt} 개")

if __name__ == "__main__":
    main()
