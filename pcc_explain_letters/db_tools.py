# db_tools.py
# Quick tools to inspect, search, load JSONL into, and export your SQLite DB.

import argparse, json, sqlite3, sys
from pathlib import Path

DB_PATH = "explain_letters.sqlite"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS explain_letters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pk TEXT UNIQUE,
    doc_no TEXT,
    subject TEXT,
    issue_date TEXT,
    category TEXT,
    content TEXT,
    url TEXT,
    source_html TEXT
);
"""

def conn():
    if not Path(DB_PATH).exists():
        print(f"[!] DB not found at {DB_PATH}. If this is unexpected, run your crawler first.")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def cmd_schema(args):
    con = conn()
    cur = con.cursor()
    # show tables
    print("== Tables ==")
    for name, in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        print(" -", name)

    # show columns for main table
    print("\n== explain_letters columns ==")
    for cid, name, ctype, notnull, dflt, pk in cur.execute("PRAGMA table_info(explain_letters)"):
        key = " (PK)" if pk else ""
        print(f" - {name} {ctype}{key}")

    con.close()

def cmd_stats(args):
    con = conn()
    cur = con.cursor()
    total = cur.execute("SELECT COUNT(*) FROM explain_letters").fetchone()[0]
    uniq = cur.execute("SELECT COUNT(DISTINCT pk) FROM explain_letters").fetchone()[0]
    print(f"Rows total: {total}")
    print(f"Unique pk:  {uniq}")
    # simple top categories by count
    print("\nTop categories:")
    for cat, c in cur.execute("""
        SELECT COALESCE(category,'(空白)'), COUNT(*) 
        FROM explain_letters 
        GROUP BY category 
        ORDER BY COUNT(*) DESC, category 
        LIMIT 10
    """):
        print(f" - {cat}: {c}")
    con.close()

def cmd_head(args):
    n = int(args.n)
    con = conn()
    cur = con.cursor()
    print(f"== First {n} rows ==")
    for row in cur.execute("""
        SELECT pk, doc_no, subject, substr(content,1,80) || '…' AS preview
        FROM explain_letters
        ORDER BY id ASC
        LIMIT ?
    """, (n,)):
        print(row)
    con.close()

def cmd_search(args):
    q = f"%{args.keyword}%"
    n = int(args.n)
    con = conn()
    cur = con.cursor()
    print(f"== Search '{args.keyword}' in subject/content (top {n}) ==")
    for row in cur.execute("""
        SELECT pk, doc_no, subject, substr(content,1,80) || '…' AS preview
        FROM explain_letters
        WHERE subject LIKE ? OR content LIKE ?
        ORDER BY id DESC
        LIMIT ?
    """, (q, q, n)):
        print(row)
    con.close()

def upsert(con, rec: dict):
    con.execute("""
    INSERT INTO explain_letters (pk, doc_no, subject, issue_date, category, content, url, source_html)
    VALUES (:pk, :doc_no, :subject, :issue_date, :category, :content, :url, :source_html)
    ON CONFLICT(pk) DO UPDATE SET
        doc_no=excluded.doc_no,
        subject=excluded.subject,
        issue_date=excluded.issue_date,
        category=excluded.category,
        content=excluded.content,
        url=excluded.url,
        source_html=excluded.source_html
    """, rec)

def cmd_load(args):
    """Load/merge a JSONL file like exports/explain_letters.jsonl (or Sinotech’s)."""
    path = Path(args.file)
    if not path.exists():
        print(f"[!] File not found: {path}")
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    con.execute(SCHEMA_SQL)  # ensures table exists
    added = updated = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            # normalize keys that we expect; tolerate missing fields
            norm = {
                "pk": rec.get("pk") or rec.get("id") or rec.get("PK"),
                "doc_no": rec.get("doc_no") or rec.get("發文字號"),
                "subject": rec.get("subject") or rec.get("主旨") or rec.get("標題"),
                "issue_date": rec.get("issue_date") or rec.get("發文日期"),
                "category": rec.get("category") or rec.get("類別") or rec.get("法規"),
                "content": rec.get("content") or rec.get("全文") or "",
                "url": rec.get("url") or "",
                "source_html": rec.get("source_html") or "",
            }
            if not norm["pk"]:
                # skip rows without a primary key
                continue
            before = con.execute("SELECT 1 FROM explain_letters WHERE pk=?", (norm["pk"],)).fetchone()
            upsert(con, norm)
            if before:
                updated += 1
            else:
                added += 1

    con.commit()
    con.close()
    print(f"Load complete: added {added}, updated {updated} from {path.name}")

def cmd_export(args):
    fmt = args.format.lower()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    con = conn()
    cur = con.cursor()
    rows = cur.execute("""
        SELECT pk, doc_no, subject, issue_date, category, content, url
        FROM explain_letters
        ORDER BY issue_date DESC, id DESC
    """).fetchall()
    cols = ["pk", "doc_no", "subject", "issue_date", "category", "content", "url"]

    if fmt == "csv":
        import csv
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"Wrote CSV: {out}")
    elif fmt == "jsonl":
        with out.open("w", encoding="utf-8") as f:
            for r in rows:
                obj = dict(zip(cols, r))
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        print(f"Wrote JSONL: {out}")
    else:
        print("[!] Supported formats: csv, jsonl")
    con.close()

def main():
    ap = argparse.ArgumentParser(description="SQLite tools for explain_letters DB")
    sub = ap.add_subparsers()

    p1 = sub.add_parser("schema", help="Show tables & columns")
    p1.set_defaults(func=cmd_schema)

    p2 = sub.add_parser("stats", help="Show counts and top categories")
    p2.set_defaults(func=cmd_stats)

    p3 = sub.add_parser("head", help="Show first N rows")
    p3.add_argument("-n", default="5")
    p3.set_defaults(func=cmd_head)

    p4 = sub.add_parser("search", help="Search subject/content")
    p4.add_argument("keyword")
    p4.add_argument("-n", default="10")
    p4.set_defaults(func=cmd_search)

    p5 = sub.add_parser("load", help="Load/merge a JSONL into DB")
    p5.add_argument("file")
    p5.set_defaults(func=cmd_load)

    p6 = sub.add_parser("export", help="Export DB to CSV or JSONL")
    p6.add_argument("format", choices=["csv", "jsonl"])
    p6.add_argument("out")
    p6.set_defaults(func=cmd_export)

    args = ap.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
