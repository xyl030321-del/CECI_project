#coding: utf-8
"""
Turning guidance Excel into JSONL (exclude "投標須知")
Inputs:Checklist01.xlsx
Outputs:out/guidance.jsonl
"""

import os, json
from pathlib import Path
import pandas as pd

IN_XLSX = "inputs/Checklist01.xlsx"
OUT_DIR = Path("out"); OUT_DIR.mkdir(parents=True, exist_ok=True)

# 3 columns in the Excel file.
COL_CLAUSE = "契約條款及相關附件"
COL_RISK = "法律潛在風險分析"
COL_AI = "AI產出審查意見與建議"

def main():
    if not os.path.exists(IN_XLSX):
        print("File not found:", IN_XLSX); return
    df = pd.read_excel(IN_XLSX, sheet_name=0, dtype=str).fillna("")
    #keep only if 3 columns are present
    missing = [c for c in [COL_CLAUSE, COL_RISK, COL_AI] if c not in df.columns]
    if missing:
        print("Missing expected columns:", missing)
        print("Columns found:", list(df.columns)); return
    df = df[[COL_CLAUSE, COL_RISK, COL_AI]]

    #drop empty rows
    df = df[df[[COL_CLAUSE, COL_RISK, COL_AI]].apply(lambda r: r.str.strip().any(), axis=1)]
    #normalize into records
    records = []
    for i, r in df.iterrows():
        records.append({
            "id": f"G{i+1:04d}",
            "clause": r[COL_CLAUSE].strip(),
            "risk":r[COL_RISK].strip(),
            "recommandation":r[COL_AI].strip(),
        })

    #write output
    out_jsonl = OUT_DIR / "checklist01.jsonl"
    with open(out_jsonl, "w", encoding= "utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} rows.")
    print("JSONL:", out_jsonl)
    

if __name__ == "__main__":
    main()