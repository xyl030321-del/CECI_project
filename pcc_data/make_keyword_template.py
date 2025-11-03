# -*- coding: utf-8 -*-
# Create a manual keyword template from clauses.csv
from pathlib import Path
import csv

BASE = Path(__file__).resolve().parent
CLAUSES = BASE / "data" / "out_csv" / "clauses.csv"
OUT = BASE / "data" / "out_csv" / "clause_keywords_manual.csv"

assert CLAUSES.exists(), f"Not found: {CLAUSES}"

rows = []
with open(CLAUSES, "r", encoding="utf-8-sig", newline="") as f:
    r = csv.DictReader(f)
    for i, row in enumerate(r, 1):
        # Short preview to help you choose keywords
        preview = (row.get("tmpl_text","") or row.get("doc_text","") or "")[:120]
        rows.append({
            "clause_id": row["clause_id"],
            "pdf_file_name": row.get("pdf_file_name",""),
            "parent_item": row.get("parent_item",""),
            "sub_item": row.get("sub_item",""),
            "preview": preview,
            "keywords": ""  # <-- fill manually; separate multiple with semicolons ;
        })

with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["clause_id","pdf_file_name","parent_item","sub_item","preview","keywords"])
    w.writeheader()
    w.writerows(rows)

print(f"✅ Template created: {OUT}")
print("Fill the 'keywords' column (use semicolons ; for multiple keywords).")