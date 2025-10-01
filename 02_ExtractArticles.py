#coding: utf-8
"""
Extract article blocks (第...條 + title + content) form DOCX.
Outputs:
    out/StandardTemp01.jsonl
    out/Contract01.jsonl
"""

import os, json
from pathlib import Path 
from docx import Document
import pdfplumber
import docx2txt

IN_DIR = Path("inputs")
OUT_DIR = Path("out"); OUT_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATE_DOCX = IN_DIR/"StandardTemp01.docx"
TARGET_DOCX =  IN_DIR/"Contract01.docx"

SKIP_FIRST_PAGE = True

SPACE_SET = {" ", "\t", "u3000", "u00A0"}
def strip_intern(s: str) -> str:
    if not s: return ""
    return "".join(ch for ch in s if ch not in SPACE_SET)

CN_NUM = {'零':0, '一':1, '二':2, '三':3, '四':4, '五':5, '六':6, '七':7, '八':8, '九':9}
CN_UNIT = {'十':10, '百':100, '千':1000}
def cn2int(s: str):
    if not s: return ""
    s = strip_intern(s)
    if s.isdigit(): return int(s)
    total = 0; num = 0; used = False
    for ch in s:
        if ch in CN_NUM: num = CN_NUM[ch]
        elif ch in CN_UNIT: 
            u = CN_UNIT[ch]
            if num == 0: num = 1
            total += num*u; num = 0; used = True
        else: return None
    total += num
    return total if (used or total != 0 or s in ("零")) else None

def read_docx_lines(path):
    doc = Document(path)
    lines = []
    for p in doc.paragraphs:
        t = (p.text or "").rstrip()
        if t.strip(): lines.append(t)
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    t = (para.text or "").rstrip()
                    if t.strip(): lines.append(t)
    return lines

# 1st page detector & filter
def page1_lines_docx(path: Path):
    """
    Return normallized lines from docx file with docx2txt pages breaker.
    """
    text = docx2txt.process(str(path)) or ""
    pages = text.split("\f")
    if not pages:
        return set()
    page1 = pages[0]
    #normalize similar to strip_intern 
    def _norm(s: str) -> str:
        return  "".join(ch for ch in s.strip() if ch not in SPACE_SET)
    return {_norm(ln) for ln in page1.splitlines() if ln.strip()}

def filter_out_page1(rich_lines, page1_norms):
    if not page1_norms:
        return rich_lines
    kept = []
    for ln in rich_lines:
        norm = "".join(ch for ch in ln.strip() if ch not in SPACE_SET)
        if norm not in page1_norms:
            kept.append(ln)
    return kept

def startswith_article(line: str):
    """
    Return (num_int, num_cn, title) or None
    """
    if not line: return None
    s = line.strip()
    if not s.startswith("第"): return None
    #find first '條'
    idx = -1
    for i, ch in enumerate(s):
        if ch == "條":
            idx = i; break
    if idx == -1: return None
    num_cn_raw = s[1:idx]
    num_cn = strip_intern(num_cn_raw)
    num_int = cn2int(num_cn)
    if num_int is None: return None

    #title after '條'
    rest = s[idx+1:]
    while rest and rest[0] in (" ", "\t", "\u3000"):
        rest = rest[1:]
    title = rest.strip()
    # allow empty title
    return (num_int, num_cn, title)

def extract_blocks(lines):
    """
    Return list of {article_no, article_no_cn, title, content}
    """
    blocks = []
    current = None
    for ln in lines:
        if ln.strip().startswith("附件"):
            continue
        hit = startswith_article(ln)
        if hit:
            no_int, no_cn, title = hit
            current = {"article_no": no_int, "article_no_cn": no_cn, "title": title, "text": ""}
            blocks.append(current)
        else:
            if current is not None:
                current["text"] += (("\n" if current["text"] else "") + ln)
    # sort by article number
    blocks.sort(key=lambda x: x["article_no"])
    return blocks

def write_jsonl(blocks, path):
    with open(path, "w", encoding = "utf-8") as f:
        for b in blocks:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")

# def skip_first_page(lines):
#     try:
#         import docx2txt
#         text = docx2txt.process(str(lines)) or ""
#         pages = text.split("\f")
#         if len(pages) > 1:
#             return [ln.strip() for ln in "\n".join(pages[1:]).splitlines() if ln.strip()]
#     except ImportError:
#         print("docx2txt is not installed.")
#     return lines

def main():
    # template_path = "inputs/StandardTemp01.docx"
    # target_path =  "inputs/Contract01.docx"

    if TEMPLATE_DOCX.exists():
        #rich extraxt
        t_lines_rich = read_docx_lines(TEMPLATE_DOCX)
        if SKIP_FIRST_PAGE:
            p1 = page1_lines_docx(TEMPLATE_DOCX)
            t_lines = filter_out_page1(t_lines_rich, p1)
    else:
        print("Standard Template not found.")
        return
    
    
    if not TARGET_DOCX.exists():
        print("Contract not found.")
        return
    g_lines_rich = read_docx_lines(TARGET_DOCX)
    if SKIP_FIRST_PAGE:
        gp1 = page1_lines_docx(TARGET_DOCX)
        g_lines = filter_out_page1(g_lines_rich, gp1)
    else:
        g_lines = g_lines_rich

    

    t_blocks = extract_blocks(t_lines)
    g_blocks = extract_blocks(g_lines)

    out_t = OUT_DIR / "StandardTemp01.jsonl"
    out_g = OUT_DIR / "Contract01.jsonl"
    write_jsonl(t_blocks, out_t)
    write_jsonl(g_blocks, out_g)

    print(f"Template articles: {len(t_blocks)} -> {out_t}")
    print(f"Target articles: {len(g_blocks)} -> {out_g}")
    if t_blocks:
        print("Template range:", t_blocks[0]["article_no"], "...", t_blocks[-1]["article_no"])
    if g_blocks:
        print("Target range:", g_blocks[0]["article_no"], "...", g_blocks[-1]["article_no"])

if __name__ == "__main__":
    main()



