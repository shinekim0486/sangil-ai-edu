import pandas as pd
import sys
from pathlib import Path

def main():
    # Path to the uploaded Excel file (artifact location)
    excel_path = Path(r"C:\Users\AISW\.gemini\antigravity\brain\f347975a-626c-43c9-938c-94ace31e494c\.user_uploaded\media_1793335420735_d73b0fb9.xlsx")
    if not excel_path.exists():
        print(f"Error: Excel file not found at {excel_path}")
        sys.exit(1)

    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f"Failed to read Excel file: {e}")
        sys.exit(1)

    print("=== Data Overview ===")
    print(f"Rows: {df.shape[0]}, Columns: {df.shape[1]}")
    print("Columns:")
    for col in df.columns:
        print(f" - {col}")

    print("\n=== Missing Values per Column ===")
    missing = df.isnull().sum()
    for col, cnt in missing.items():
        print(f"{col}: {cnt}")

    print("\n=== Duplicate Row Count ===")
    dup_count = df.duplicated().sum()
    print(f"Duplicate rows: {dup_count}")

    # Basic numeric stats
    numeric_cols = df.select_dtypes(include='number').columns
    if len(numeric_cols):
        print("\n=== Numeric Columns Statistics ===")
        print(df[numeric_cols].describe())
    else:
        print("\nNo numeric columns to describe.")

    # Example: check for any empty strings in object columns
    object_cols = df.select_dtypes(include='object').columns
    if len(object_cols):
        print("\n=== Empty String Checks (object columns) ===")
        for col in object_cols:
            empty_str_cnt = (df[col] == "").sum()
            if empty_str_cnt:
                print(f"{col}: {empty_str_cnt} empty strings")

if __name__ == "__main__":
    main()
