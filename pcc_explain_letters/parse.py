from bs4 import BeautifulSoup
import re

def _norm(s): return re.sub(r"\s+", " ", s or "").strip()

def kv_from_tables(soup):
    """Return list of (label, value) pairs from any th/td tables."""
    out = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th","td"])
            if len(cells) >= 2:
                label = _norm(cells[0].get_text(" ", strip=True))
                value = _norm(cells[1].get_text(" ", strip=True))
                if label and value:
                    out.append((label, value))
    return out

def parse_detail(html, url, pk):
    soup = BeautifulSoup(html, "lxml")

    # try structured tables first
    kv = dict(kv_from_tables(soup))

    # common fields (names vary per page; cover typical variants)
    doc_no = kv.get("發文字號") or kv.get("發文字號：") or ""
    subject = kv.get("主旨") or kv.get("要旨") or kv.get("標題") or ""
    issue_date = kv.get("發文日期") or kv.get("發文日") or ""
    category = kv.get("法規") or kv.get("類別") or ""

    # fallbacks from headings/blobs
    if not subject:
        h = soup.find(["h1","h2","h3"])
        subject = _norm(h.get_text()) if h else ""

    # content block: try rich “內容/說明” cells, else take main text
    content_candidates = []
    for label_key in ("內容", "說明", "函釋內容", "全文"):
        for (k, v) in kv.items():
            if label_key in k:
                content_candidates.append(v)
    if not content_candidates:
        # take the largest paragraph-ish block
        paras = [p.get_text(" ", strip=True) for p in soup.find_all(["p","div","td"])]
        content_candidates = sorted(paras, key=len, reverse=True)[:1]

    rec = {
        "pk": pk,
        "doc_no": _norm(doc_no),
        "subject": _norm(subject),
        "issue_date": _norm(issue_date),
        "category": _norm(category),
        "content": _norm("\n\n".join(content_candidates)),
        "url": url,
        "source_html": html
    }
    return rec

# --- v2 section-aware parser for "檢視" page ---


def _clean(s): 
    return re.sub(r"\s+", " ", s or "").strip()

LABELS = ["發文日期", "發文字號", "根據", "主旨", "說明"]

def parse_detail_v2(html: str, url: str, pk: str):
    """
    Extract: ID(=pk), 發文日期, 發文字號, 根據, 主旨, 說明 from the detail page.
    Logic:
      - prefer <b>發文日期：...> patterns
      - for '說明', capture the paragraph block after its heading until the next heading/footer
    """
    soup = BeautifulSoup(html, "lxml")

    # 1) direct <b>Label：Value> picks
    fields = { "ID": pk, "發文日期": "", "發文字號": "", "根據": "", "主旨": "", "說明": "" }

    # A) read all bold tags as potential labeled lines (some pages use <b>…</b> labels)
    for b in soup.find_all(["b", "strong"]):
        txt = _clean(b.get_text())
        # normalize fullwidth/halfwidth colon
        txt = txt.replace("：", ":")
        for lab in LABELS:
            if txt.startswith(lab + ":"):
                val = _clean(txt.split(":", 1)[1])
                if lab in ("發文日期", "發文字號", "根據", "主旨") and not fields[lab]:
                    fields[lab] = val

    # B) fallback: two-column tables (th/td) sometimes repeat the same info
    for tr in soup.find_all("tr"):
        tds = tr.find_all(["th","td"])
        if len(tds) >= 2:
            lab = _clean(tds[0].get_text())
            val = _clean(tds[1].get_text())
            lab = lab.replace("：", "").strip()
            if lab in ("發文日期", "發文字號", "根據", "主旨") and val and not fields.get(lab):
                fields[lab] = val

    # 2) 說明 section
    # Strategy: find a heading node whose text starts with "說明" (b/strong/th), 
    # then collect subsequent siblings’ text until the next bold heading or section break.
    def collect_following_paragraphs(start_tag):
        buf = []
        # walk through next siblings, collecting block-level text
        for sib in start_tag.next_siblings:
            # stop at the next bold/strong that looks like another heading or at long horizontal rule/footers
            if getattr(sib, "name", None) in ("b","strong","h1","h2","h3","th"):
                t = _clean(sib.get_text())
                if any(t.startswith(l + ":") or t == l for l in LABELS):
                    break
            if getattr(sib, "name", None) in ("hr",):
                break
            if hasattr(sib, "get_text"):
                text = _clean(sib.get_text(" ", strip=True))
                if text:
                    buf.append(text)
        return "\n\n".join(buf).strip()

    # try bold/strong as section header
    explain_text = ""
    for tag in soup.find_all(["b","strong","th"]):
        t = _clean(tag.get_text()).replace("：", ":")
        if t.startswith("說明"):
            explain_text = collect_following_paragraphs(tag)
            break

    # final fallbacks for 說明:
    if not explain_text:
        # the page often has the body paragraphs after “主旨”；take the largest paragraph block
        paras = [ _clean(p.get_text(" ", strip=True)) for p in soup.find_all(["p","div","td"]) ]
        paras = [p for p in paras if len(p) > 40]  # avoid tiny crumbs
        if paras:
            explain_text = max(paras, key=len)

    fields["說明"] = explain_text

    # normalize “中華民國 … 年 … 月 … 日” into original text (we keep original format as you wanted)
    # If you want ISO date later, you can add a converter here.

    # Return both Chinese-key dict (for export/presentation) and a normalized dict (for DB)
    normalized = {
        "pk": pk,
        "issue_date": fields["發文日期"],
        "doc_no": fields["發文字號"],
        "basis": fields["根據"],
        "subject": fields["主旨"],
        "description": fields["說明"],
        "url": url,
        "source_html": html
    }
    return fields, normalized
