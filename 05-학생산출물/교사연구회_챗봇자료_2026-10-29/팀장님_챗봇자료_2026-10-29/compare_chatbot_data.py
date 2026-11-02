import pandas as pd
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Configure logger to output JSON lines to stdout
logger = logging.getLogger("compare_logger")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.handlers = []
logger.addHandler(handler)

def log(event: str, **kwargs):
    """Emit a JSON‑line log entry.
    Args:
        event: Short identifier for the log type (e.g., 'overview', 'missing')
        **kwargs: Additional fields to include.
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": "info",
        "event": event,
        **kwargs,
    }
    logger.info(json.dumps(entry, ensure_ascii=False))

def load_excel(path: Path, name: str):
    if not path.exists():
        log("error", message=f"{name} Excel file not found", path=str(path))
        sys.exit(1)
    try:
        df = pd.read_excel(path)
        log("load_success", message=f"Loaded {name}", rows=df.shape[0], cols=df.shape[1])
        return df
    except Exception as e:
        log("error", message=f"Failed to read {name}", error=str(e))
        sys.exit(1)

def diff_overview(df1: pd.DataFrame, df2: pd.DataFrame, name1: str, name2: str):
    log(
        "overview",
        name1=name1,
        rows1=df1.shape[0],
        cols1=df1.shape[1],
        name2=name2,
        rows2=df2.shape[0],
        cols2=df2.shape[1],
    )
    cols1 = set(df1.columns)
    cols2 = set(df2.columns)
    only_in_1 = sorted(cols1 - cols2)
    only_in_2 = sorted(cols2 - cols1)
    if only_in_1:
        log("column_diff", side=name1, columns=only_in_1)
    if only_in_2:
        log("column_diff", side=name2, columns=only_in_2)
    log("common_columns", count=len(cols1 & cols2))

def diff_missing(df1: pd.DataFrame, df2: pd.DataFrame, name1: str, name2: str):
    miss1 = df1.isnull().sum()
    miss2 = df2.isnull().sum()
    for col in sorted(set(df1.columns) & set(df2.columns)):
        if miss1[col] != miss2[col]:
            log(
                "missing_diff",
                column=col,
                missing1=int(miss1[col]),
                missing2=int(miss2[col]),
                name1=name1,
                name2=name2,
            )

def diff_duplicates(df: pd.DataFrame, name: str):
    dup = int(df.duplicated().sum())
    log("duplicates", name=name, duplicate_rows=dup)

def diff_values(df1: pd.DataFrame, df2: pd.DataFrame, name1: str, name2: str):
    df1_al = df1.reset_index(drop=True)
    df2_al = df2.reset_index(drop=True)
    min_len = min(len(df1_al), len(df2_al))
    common_cols = list(set(df1_al.columns) & set(df2_al.columns))
    diffs = []
    for i in range(min_len):
        row1 = df1_al.iloc[i][common_cols]
        row2 = df2_al.iloc[i][common_cols]
        if not row1.equals(row2):
            diffs.append((i, row1, row2))
            if len(diffs) >= 20:
                break
    if diffs:
        for idx, r1, r2 in diffs:
            diff_detail = {}
            for col in common_cols:
                v1, v2 = r1[col], r2[col]
                if pd.isna(v1) and pd.isna(v2):
                    continue
                if v1 != v2:
                    diff_detail[col] = {"first": v1, "second": v2}
            log(
                "row_diff",
                row_index=idx,
                differences=diff_detail,
                name1=name1,
                name2=name2,
            )
    else:
        log("row_diff", message="No differences in first {} rows".format(min_len))

def main():
    # Paths to the two uploaded Excel files (artifact location)
    path1 = Path(r"C:\Users\AISW\.gemini\antigravity\brain\f347975a-626c-43c9-938c-94ace31e494c\.user_uploaded\media_1793335420735_d73b0fb9.xlsx")
    path2 = Path(r"C:\Users\AISW\.gemini\antigravity\brain\f347975a-626c-43c9-938c-94ace31e494c\.user_uploaded\media_1793335443319_a4430583.xlsx")
    df1 = load_excel(path1, "First")
    df2 = load_excel(path2, "Second")

    diff_overview(df1, df2, "First", "Second")
    diff_missing(df1, df2, "First", "Second")
    diff_duplicates(df1, "First")
    diff_duplicates(df2, "Second")
    diff_values(df1, df2, "First", "Second")

if __name__ == "__main__":
    main()
