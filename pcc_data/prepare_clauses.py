# -*- coding: utf-8 -*-
"""
Read contracts/compare_result.json and produce:
- data/out_csv/clauses.csv            (one row per clause)
- data/out_csv/clause_keywords.csv    (clause_id -> keyword)
Keywords are simple extractions for '…法', '…辦法', and '第X條/第Y項' patterns.
"""

import json, csv, re
from pathlib import Path

BASE = Path(__file__).resolve().parent
INP  = BASE / "data" / "contracts" / "compare_result.json"
OUTD = BASE / "data" / "out_csv"
OUTD.mkdir(parents=True, exist_ok=True)

CLAUSES_CSV  = OUTD / "clauses.csv"
CKW_CSV      = OUTD / "clause_keywords.csv"

assert INP.exists(), f"Not found: {INP}"

with open(INP, "r", encoding="utf-8") as f:
    data = json.load(f)

def norm(s):
    if not isinstance(s, str):
        return ""
    s = s.replace("\u3000"," ").replace("\xa0"," ").strip()
    return re.sub(r"[ \t]+", " ", s)

# Patterns to capture law-ish names & clauses
PAT_LAWNAME = re.compile(r"([^\s，。；；、\n]{2,20}?(法|辦法))")
PAT_CLAUSE  = re.compile(r"(第\d+條(?:第\d+項)?)")

rows = []
kw_rows = []
cid = 0

for item in data:
    cid += 1
    clause_id = f"C{cid:04d}"

    pdf_file_name = norm(item.get("pdf_file_name",""))
    parent_item   = norm(item.get("parent_item",""))
    sub_item      = norm(item.get("sub_item",""))
    tmpl_text     = norm(item.get("範本內容",""))
    doc_text      = norm(item.get("文件內容",""))
    diff_type     = norm(item.get("差異類型",""))
    change_text   = norm(item.get("文字改動",""))
    llm_judge     = norm(item.get("LLM判斷",""))

    full = " ".join([tmpl_text, doc_text, change_text])

    # Extract candidate keywords
    kws = set()
    for m in PAT_LAWNAME.finditer(full):
        kws.add(m.group(1))
    for m in PAT_CLAUSE.finditer(full):
        kws.add(m.group(1))

    # row for the clause itself
    rows.append({
        "clause_id": clause_id,
        "pdf_file_name": pdf_file_name,
        "parent_item": parent_item,
        "sub_item": sub_item,
        "diff_type": diff_type,
        "tmpl_text": tmpl_text,
        "doc_text": doc_text,
        "change_text": change_text,
        "llm_judgement": llm_judge
    })

    # rows for clause -> keyword mapping
    for kw in sorted(kws):
        kw_rows.append({"clause_id": clause_id, "keyword": kw})

# Write CSVs (UTF-8 with BOM for Excel-friendly viewing)
def write_csv(path, fieldnames, data_rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(data_rows)

write_csv(CLAUSES_CSV,
          ["clause_id","pdf_file_name","parent_item","sub_item",
           "diff_type","tmpl_text","doc_text","change_text","llm_judgement"],
          rows)

write_csv(CKW_CSV, ["clause_id","keyword"], kw_rows)

print(f"✅ clauses: {len(rows)} | clause_keywords: {len(kw_rows)}")
print(f"→ {CLAUSES_CSV}")
print(f"→ {CKW_CSV}")