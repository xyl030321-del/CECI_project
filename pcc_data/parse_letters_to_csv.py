# -*- coding: utf-8 -*-
"""
Parse PCC explain-letter TXT files into structured outputs:
- data/out_csv/letters.csv / letters.json / letters.xlsx
- data/out_csv/legal_basis.csv (unique laws/clauses)
- data/out_csv/letter_law.csv (Letter -> Law links)

Key fixes:
- Handles 「根據」 or 「依據」 with OR without a colon (：).
- Each section (發文日期/發文字號/主旨/本解釋函上網公告者/附件/根據/依據) stops at the *next header*.
- Legal basis pieces split by 、，,；; and extract 第X條 / 第Y項 when present.
"""

import re, csv, json, hashlib
from pathlib import Path

# Optional: for Excel export
try:
    import pandas as pd
except Exception:
    pd = None

BASE_DIR = Path(__file__).resolve().parent
IN_DIR = BASE_DIR / "data" / "letters_txt"
OUT_DIR = BASE_DIR / "data" / "out_csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Recognized headers (add more if your files use variants)
HEADERS = r"(發文日期|發文字號|根據|依據|本解釋函上網公告者|附件|主旨)"
SEP = r"[:：]?"  # colon optional

# ---------- helpers ----------
def norm_spaces(s: str) -> str:
    # collapse full-width spaces and NBSP, then trim
    s = s.replace("\u3000", " ").replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def roc_to_iso(text: str) -> str:
    """
    Convert 中華民國YYY年M月D日 -> YYYY-MM-DD
    Accepts stray spaces.
    """
    m = re.search(r"中華民國\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日", text)
    if not m:
        return ""
    y, mth, d = map(int, m.groups())
    return f"{y + 1911:04d}-{mth:02d}-{d:02d}"

def grab(label: str, content: str) -> str:
    """
    Capture text after '<label>：' OR '<label> ' (colon optional)
    up to the next header (from HEADERS) OR end of file.
    Works across multiple lines.
    """
    pattern = rf"{label}{SEP}\s*(.+?)(?=\r?\n{HEADERS}{SEP}|\Z)"
    m = re.search(pattern, content, flags=re.DOTALL)
    return m.group(1).strip() if m else ""

def parse_attachments(text: str):
    payload = grab("附件", text)
    if not payload:
        return []
    parts = re.split(r"[、，,；;]\s*", payload)
    out = []
    for p in parts:
        p = p.strip(" ；;，,。．.")
        if p:
            out.append(p)
    return out

def parse_legal_basis(full_text: str):
    """
    Prefer '根據', fallback '依據'. Return list of raw law pieces.
    """
    payload = grab("根據", full_text)
    if not payload:
        payload = grab("依據", full_text)
    if not payload:
        return []
    parts = re.split(r"[、，,；;]\s*", payload)
    return [p.strip(" ；;，,。．.") for p in parts if p.strip()]

def split_law_piece(piece: str):
    """
    Extract law_name + 第X條 + 第Y項 (Y optional).
    Example: '機關委託技術服務廠商評選及計費辦法第23條第1項'
    If not match, keep the whole piece as law_name.
    """
    m = re.match(r"(.+?)第(\d+)條(?:第(\d+)項)?", piece)
    if m:
        name = norm_spaces(m.group(1))
        art = f"第{m.group(2)}條"
        para = f"第{m.group(3)}項" if m.group(3) else ""
        return name, art, para
    return norm_spaces(piece), "", ""

# ---------- main parse ----------
letters_rows = []
legal_basis_rows = []
letter_law_rows = []
law_key_to_id = {}

txt_files = sorted(IN_DIR.glob("*.txt"))

for fp in txt_files:
    text = fp.read_text(encoding="utf-8", errors="ignore")

    # Sections (each stops at the next header)
    roc_date_raw = norm_spaces(grab("發文日期", text))
    doc_no       = norm_spaces(grab("發文字號", text))
    subject      = norm_spaces(grab("主旨", text))
    issuer       = norm_spaces(grab("本解釋函上網公告者", text))

    letters_rows.append({
        "file": fp.name,
        "roc_date": roc_date_raw,
        "date_iso": roc_to_iso(roc_date_raw),
        "doc_no": doc_no,
        "subject": subject,
        "issuer": issuer
    })

    # Legal basis -> laws + links
    for piece in parse_legal_basis(text):
        lname, art, para = split_law_piece(piece)
        key = (lname, art, para)
        if key not in law_key_to_id:
            law_id = hashlib.sha1(("||".join(key)).encode("utf-8")).hexdigest()[:12]
            law_key_to_id[key] = law_id
            legal_basis_rows.append({
                "law_id": law_id,
                "law_name": lname,
                "article": art,
                "paragraph": para,
                "raw_text": piece
            })
        letter_law_rows.append({
            "file": fp.name,
            "law_id": law_key_to_id[key]
        })

# ---------- write outputs ----------
def write_csv(path: Path, fieldnames, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

# letters
write_csv(
    OUT_DIR / "letters.csv",
    ["file", "roc_date", "date_iso", "doc_no", "subject", "issuer"],
    letters_rows
)

if pd is not None:
    pd.DataFrame(legal_basis_rows, columns=["law_id","law_name","article","paragraph","raw_text"])\
      .to_excel(OUT_DIR / "legal_basis.xlsx", index=False)
    pd.DataFrame(letter_law_rows, columns=["file","law_id"])\
      .to_excel(OUT_DIR / "letter_law.xlsx", index=False)


# JSON
with open(OUT_DIR / "letters.json", "w", encoding="utf-8") as f:
    json.dump(letters_rows, f, ensure_ascii=False, indent=2)

# Excel (optional)
if pd is not None:
    pd.DataFrame(letters_rows, columns=["file", "roc_date", "date_iso", "doc_no", "subject", "issuer"])\
      .to_excel(OUT_DIR / "letters.xlsx", index=False)

# laws + links
write_csv(
    OUT_DIR / "legal_basis.csv",
    ["law_id", "law_name", "article", "paragraph", "raw_text"],
    legal_basis_rows
)
write_csv(
    OUT_DIR / "letter_law.csv",
    ["file", "law_id"],
    letter_law_rows
)

print(f"✅ letters: {len(letters_rows)} | laws: {len(legal_basis_rows)} | links: {len(letter_law_rows)}")
print(f"Outputs in: {OUT_DIR}")
