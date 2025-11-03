# -*- coding: utf-8 -*-
"""
From contracts/compare_result.json:
- Build clauses.csv (one row per clause)
- Build clause_law.csv (Clause -> Law links) by extracting law mentions from text

Key points:
- Snap every detected law name to the official name from data/out_csv/legal_basis.csv
  (e.g., '採購法' -> '政府採購法'), using:
    * alias dictionary (quick exact maps), then
    * longest-match containment against whitelist (robust fallback)
- Keep ONLY pure regulation names (…法/…辦法/…條例/…規則/…準則)
- Capture 第X條 / 第X條第Y項, lists (第3條、第5條), ranges (第3條至第5條 / ~ / - / —)
- Support 本法 / 本辦法 / 本條例 / 本規則 / 本準則 (refers to last explicit law)
- Output CSV in UTF-8 with BOM for Excel
"""

from pathlib import Path
import json, csv, re, hashlib

BASE = Path(__file__).resolve().parent
INP_JSON  = BASE / "data" / "contracts" / "compare_result.json"
INP_LAWS  = BASE / "data" / "out_csv" / "legal_basis.csv"   # whitelist of official laws/clauses
OUTD      = BASE / "data" / "out_csv"
OUTD.mkdir(parents=True, exist_ok=True)

CLAUSES_CSV     = OUTD / "clauses.csv"
CLAUSE_LAW_CSV  = OUTD / "clause_law.csv"

assert INP_JSON.exists(), f"Not found: {INP_JSON}"
assert INP_LAWS.exists(), f"Not found: {INP_LAWS} (run parse_letters_to_csv.py first)"

# ----------------- helpers -----------------
def norm(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.replace("\u3000"," ").replace("\xa0"," ").replace(""," ")
    s = re.sub(r"[ \t]+", " ", s)
    # normalize odd duplicates like "第7條條" → "第7條"
    s = re.sub(r"(第\s*\d+\s*條)\s*條", r"\1", s)
    return s.strip()

def strip_brackets(s: str) -> str:
    return re.sub(r"[()（）\[\]【】〈〉《》<>「」『』]", "", s)

def canonical(s: str) -> str:
    s = strip_brackets(norm(s))
    s = re.sub(r"\s+", "", s)
    return s

def clean_prefixes(s: str) -> str:
    s = norm(s)
    # drop common leading verbs/prefixes
    return re.sub(r"^(依據|依照|依|按|符合|就|關於)\s*", "", s)

def clean_law_token(s: str) -> str:
    """Return the inner token that ends with 法/辦法/條例/規則/準則."""
    s = clean_prefixes(s)
    tokens = re.findall(r"([^\s，。、；\n]{2,80}?(?:法|辦法|條例|規則|準則))", s)
    return tokens[-1] if tokens else ""

def law_id_from(law_name: str, article: str, paragraph: str) -> str:
    key = (law_name, article, paragraph)
    return hashlib.sha1(("||".join(key)).encode("utf-8")).hexdigest()[:12]

# ----------------- load whitelist of laws -----------------
known_laws = []      # display names
known_canon = []     # canonical (no spaces/brackets)
with open(INP_LAWS, "r", encoding="utf-8-sig", newline="") as f:
    r = csv.DictReader(f)
    for row in r:
        name = norm(row.get("law_name",""))
        if not name:
            continue
        known_laws.append(name)
        known_canon.append(canonical(name))

# Quick exact alias map (extend as needed)
ALIASES = {
    "採購法": "政府採購法",
    "最有利標評選辦法": "最有利標評選辦法",
    "中央機關未達公告金額採購招標辦法": "中央機關未達公告金額採購招標辦法",
    "押標金保證金暨其他擔保作業辦法": "押標金保證金暨其他擔保作業辦法",
    "採購評選委員會組織準則": "採購評選委員會組織準則",
    # add shortcuts your data uses frequently...
}

def map_to_official(law_name_raw: str) -> str:
    """
    Map a noisy/short law token to the best official name:
      1) exact alias map
      2) longest-match containment with whitelist (either direction)
    Return '' if nothing fits (reject noisy false positives).
    """
    token = clean_law_token(law_name_raw)
    if not token:
        return ""
    if token in ALIASES:
        return ALIASES[token]

    tc = canonical(token)
    if not tc:
        return ""

    candidates = []
    for name, can in zip(known_laws, known_canon):
        if tc in can or can in tc:
            candidates.append((len(can), name))
    if not candidates:
        return ""
    candidates.sort(reverse=True)  # longest official name wins
    return candidates[0][1]

# ----------------- patterns -----------------
LAW_NAME_RE   = re.compile(r"([^\s，。、；\n]{2,80}?(?:法|辦法|條例|規則|準則))")
ALIAS_RE      = re.compile(r"(本法|本辦法|本條例|本規則|本準則)")
ARTICLE_RE    = re.compile(r"第\s*(\d+)\s*條(?:\s*第\s*(\d+)\s*項)?")
ARTICLE_RANGE = re.compile(r"第\s*(\d+)\s*條\s*(?:至|~|-|—)\s*第\s*(\d+)\s*條")

def expand_article_range(a: str, b: str):
    a_i, b_i = int(a), int(b)
    if a_i > b_i:
        a_i, b_i = b_i, a_i
    return [f"第{i}條" for i in range(a_i, b_i + 1)]

def collect_articles(chunk: str):
    results = []
    # ranges
    for rg in ARTICLE_RANGE.finditer(chunk):
        for art in expand_article_range(rg.group(1), rg.group(2)):
            results.append((art, ""))
    # explicit tokens
    for m in ARTICLE_RE.finditer(chunk):
        art = f"第{m.group(1)}條"
        para = f"第{m.group(2)}項" if m.group(2) else ""
        results.append((art, para))
    # de-dup
    seen = set(); out = []
    for art, para in results:
        k = (art, para)
        if k not in seen:
            seen.add(k); out.append((art, para))
    return out

def scan_mentions(text: str, lookahead_chars: int = 420):
    """
    Walk text; at each explicit name or alias:
      - map to official law name (whitelist),
      - scan forward for articles/ranges,
      - yield (official_name, article, paragraph, raw)
    """
    last_official = None
    i = 0
    L = len(text)
    while i < L:
        m_name  = LAW_NAME_RE.search(text, i)
        m_alias = ALIAS_RE.search(text, i)

        m = None; use_alias = False
        if m_name and m_alias:
            if m_name.start() <= m_alias.start():
                m = m_name
            else:
                m = m_alias; use_alias = True
        elif m_name:
            m = m_name
        elif m_alias:
            m = m_alias; use_alias = True
        else:
            break

        start, end = m.start(), m.end()

        if not use_alias:
            official = map_to_official(m.group(1))
            if official:
                last_official = official
                chunk = text[end:end+lookahead_chars]
                arts = collect_articles(chunk)
                if arts:
                    for art, para in arts:
                        raw = f"{official}{art}{para}" if para else f"{official}{art}"
                        yield (official, art, para, raw)
                else:
                    # bare law mention still useful
                    yield (official, "", "", official)
        else:
            if last_official:
                chunk = text[end:end+lookahead_chars]
                arts = collect_articles(chunk)
                if arts:
                    for art, para in arts:
                        raw = f"{m.group(1)}{art}{para}" if para else f"{m.group(1)}{art}"
                        yield (last_official, art, para, raw)
                # else: alias without nearby article → skip
        i = end

# ----------------- main -----------------
data = json.load(open(INP_JSON, "r", encoding="utf-8"))

clause_rows = []
link_rows   = []
cid = 0

for item in data:
    cid += 1
    clause_id = f"C{cid:04d}"

    def g(k): return norm(item.get(k, ""))

    pdf_file_name = g("pdf_file_name")
    parent_item   = g("parent_item")
    sub_item      = g("sub_item")
    tmpl_text     = g("範本內容")
    doc_text      = g("文件內容")
    change_text   = g("文字改動")

    preview_src = (tmpl_text or doc_text or change_text)
    preview = preview_src[:300] if preview_src else ""
    clause_rows.append({
        "clause_id": clause_id,
        "pdf_file_name": pdf_file_name,
        "parent_item": parent_item,
        "sub_item": sub_item,
        "preview": preview
    })

    full = norm(" ".join([tmpl_text, doc_text, change_text]))
    for official_name, art, para, raw in scan_mentions(full, lookahead_chars=420):
        # keep only mapped (official) names
        if not official_name:
            continue
        lid = law_id_from(official_name, art, para)
        link_rows.append({
            "clause_id": clause_id,
            "law_id": lid,
            "law_name": official_name,
            "article": art,
            "paragraph": para,
            "raw": raw
        })

# de-duplicate links by (clause_id, law_name, article, paragraph)
seen = set(); dedup = []
for r in link_rows:
    k = (r["clause_id"], r["law_name"], r["article"], r["paragraph"])
    if k not in seen:
        seen.add(k); dedup.append(r)
link_rows = dedup

def write_csv(path: Path, fieldnames, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader(); w.writerows(rows)

write_csv(
    CLAUSES_CSV,
    ["clause_id","pdf_file_name","parent_item","sub_item","preview"],
    clause_rows
)
write_csv(
    CLAUSE_LAW_CSV,
    ["clause_id","law_id","law_name","article","paragraph","raw"],
    link_rows
)

print(f"✅ clauses: {len(clause_rows)} | clause-law links: {len(link_rows)}")
print(f"→ {CLAUSES_CSV}")
print(f"→ {CLAUSE_LAW_CSV}")