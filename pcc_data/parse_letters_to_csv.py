# parse_letters_to_csv.py
import re, csv, json
from pathlib import Path

# Optional: pandas for Excel export
try:
    import pandas as pd
except ImportError:
    pd = None

BASE_DIR = Path(__file__).resolve().parent
IN_DIR = BASE_DIR / "data" / "letters_txt"
OUT_DIR = BASE_DIR / "data" / "out_csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = r"(發文日期|發文字號|根據|本解釋函上網公告者|附件|主旨)"
SEP = r"[:：]"

def roc_to_iso(text: str) -> str:
    m = re.search(r"中華民國\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日", text)
    if not m:
        return ""
    y, mth, d = map(int, m.groups())
    return f"{y+1911:04d}-{mth:02d}-{d:02d}"

def grab(label: str, content: str) -> str:
    # Capture after "<label>：" up to the next header or EOF (multiline)
    pattern = rf"{label}{SEP}\s*(.+?)(?=\r?\n{HEADERS}{SEP}|\Z)"
    m = re.search(pattern, content, flags=re.DOTALL)
    return m.group(1).strip() if m else ""

def norm(s: str) -> str:
    return re.sub(r"[ \t\u3000\xa0]+", " ", s).strip()

rows = []
txt_files = sorted(IN_DIR.glob("*.txt"))
for p in txt_files:
    text = p.read_text(encoding="utf-8", errors="ignore")

    roc_date_raw = norm(grab("發文日期", text))
    doc_no       = norm(grab("發文字號", text))
    subject      = norm(grab("主旨", text))
    issuer       = norm(grab("本解釋函上網公告者", text))

    rows.append({
        "file": p.name,
        "roc_date": roc_date_raw,
        "date_iso": roc_to_iso(roc_date_raw),
        "doc_no": doc_no,
        "subject": subject,
        "issuer": issuer
    })

# --- CSV ---
csv_path = OUT_DIR / "letters.csv"
with open(csv_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["file","roc_date","date_iso","doc_no","subject","issuer"])
    writer.writeheader()
    writer.writerows(rows)

# --- JSON ---
json_path = OUT_DIR / "letters.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)

# --- XLSX (requires pandas & openpyxl) ---
xlsx_path = OUT_DIR / "letters.xlsx"
if pd is None:
    print("ℹ️ pandas not installed — skipping Excel export. Install with: pip install pandas openpyxl")
else:
    df = pd.DataFrame(rows, columns=["file","roc_date","date_iso","doc_no","subject","issuer"])
    # index=False keeps Excel clean; requires openpyxl as engine
    df.to_excel(xlsx_path, index=False)
    print(f"📄 Excel written to: {xlsx_path}")

print(f"✅ CSV written to:   {csv_path}")
print(f"✅ JSON written to:  {json_path}")
print(f"Total letters parsed: {len(rows)}")

# parse_letters_to_csv.py
import re, csv, json, hashlib
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None

BASE_DIR = Path(__file__).resolve().parent
IN_DIR = BASE_DIR / "data" / "letters_txt"
OUT_DIR = BASE_DIR / "data" / "out_csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = r"(發文日期|發文字號|根據|本解釋函上網公告者|附件|主旨)"
SEP = r"[:：]"

def roc_to_iso(text: str) -> str:
    m = re.search(r"中華民國\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日", text)
    if not m: return ""
    y, mth, d = map(int, m.groups())
    return f"{y+1911:04d}-{mth:02d}-{d:02d}"

def grab(label: str, content: str) -> str:
    pat = rf"{label}{SEP}\s*(.+?)(?=\r?\n{HEADERS}{SEP}|\Z)"
    m = re.search(pat, content, flags=re.DOTALL)
    return m.group(1).strip() if m else ""

def norm(s: str) -> str:
    return re.sub(r"[ \t\u3000\xa0]+", " ", s).strip()

def parse_legal_basis(line: str):
    """Split the '根據 …' line into individual law pieces."""
    if not line: return []
    # cut the leading '根據' if present
    line = re.sub(r"^\s*根據\s*", "", line)
    parts = re.split(r"[、，,；;]\s*", line)
    return [p.strip(" ；;，,。．.") for p in parts if p.strip()]

def split_law_piece(piece: str):
    """
    Extract: law_name + 第X條 + 第Y項 (第Y項 may be absent)
    Fallback: keep everything as name if pattern not found.
    """
    m = re.match(r"(.+?)第(\d+)條(?:第(\d+)項)?", piece)
    if m:
        name = m.group(1).strip()
        art  = f"第{m.group(2)}條"
        para = f"第{m.group(3)}項" if m.group(3) else ""
        return name, art, para
    return piece.strip(), "", ""

letters_rows = []
legal_basis_rows = []
letter_law_rows = []
law_key_to_id = {}

txt_files = sorted(IN_DIR.glob("*.txt"))
for p in txt_files:
    text = p.read_text(encoding="utf-8", errors="ignore")

    roc_date_raw = norm(grab("發文日期", text))
    doc_no       = norm(grab("發文字號", text))
    subject      = norm(grab("主旨", text))
    issuer       = norm(grab("本解釋函上網公告者", text))
    basis_line   = norm(grab("根據", text))

    letters_rows.append({
        "file": p.name,
        "roc_date": roc_date_raw,
        "date_iso": roc_to_iso(roc_date_raw),
        "doc_no": doc_no,
        "subject": subject,
        "issuer": issuer
    })

    # Parse & collect laws
    for piece in parse_legal_basis(basis_line):
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
            "file": p.name,
            "law_id": law_key_to_id[key]
        })

# --- letters: CSV/JSON/XLSX ---
csv_letters = OUT_DIR / "letters.csv"
with open(csv_letters, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["file","roc_date","date_iso","doc_no","subject","issuer"])
    w.writeheader(); w.writerows(letters_rows)

json_letters = OUT_DIR / "letters.json"
with open(json_letters, "w", encoding="utf-8") as f:
    json.dump(letters_rows, f, ensure_ascii=False, indent=2)

if pd is not None:
    xlsx_letters = OUT_DIR / "letters.xlsx"
    pd.DataFrame(letters_rows).to_excel(xlsx_letters, index=False)

# --- laws: CSV only (simple & import-ready) ---
csv_laws = OUT_DIR / "legal_basis.csv"
with open(csv_laws, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["law_id","law_name","article","paragraph","raw_text"])
    w.writeheader(); w.writerows(legal_basis_rows)

csv_link = OUT_DIR / "letter_law.csv"
with open(csv_link, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["file","law_id"])
    w.writeheader(); w.writerows(letter_law_rows)

print("✅ letters.csv / letters.json / letters.xlsx (if pandas) created.")
print("✅ legal_basis.csv / letter_law.csv created.")
print(f"Letters: {len(letters_rows)} | Laws: {len(legal_basis_rows)} | Links: {len(letter_law_rows)}")