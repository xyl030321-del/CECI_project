# migrate_to_v2.py
import sqlite3
from pathlib import Path
from parse import parse_detail_v2

DB_PATH = "explain_letters.sqlite"

SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS explain_letters_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pk TEXT UNIQUE,
    issue_date TEXT,        -- 發文日期 (原樣)
    doc_no TEXT,            -- 發文字號
    basis TEXT,             -- 根據
    subject TEXT,           -- 主旨
    description TEXT,       -- 說明
    url TEXT,
    source_html TEXT
);
"""

VIEW_CN = """
CREATE VIEW IF NOT EXISTS explain_letters_cn AS
SELECT 
    pk AS "ID",
    issue_date AS "發文日期",
    doc_no AS "發文字號",
    basis AS "根據",
    subject AS "主旨",
    description AS "說明",
    url AS "來源網址"
FROM explain_letters_v2;
"""

def main():
    if not Path(DB_PATH).exists():
        raise SystemExit("DB not found. Run the crawler first.")

    con = sqlite3.connect(DB_PATH)
    con.execute(SCHEMA_V2)

    # read all existing rows with HTML to re-parse precisely
    cur = con.execute("SELECT pk, url, source_html FROM explain_letters WHERE source_html IS NOT NULL AND source_html != ''")
    rows = cur.fetchall()

    inserted = updated = 0
    for pk, url, html in rows:
        fields_cn, rec = parse_detail_v2(html, url, pk)
        before = con.execute("SELECT 1 FROM explain_letters_v2 WHERE pk=?", (pk,)).fetchone()
        con.execute("""
            INSERT INTO explain_letters_v2 (pk, issue_date, doc_no, basis, subject, description, url, source_html)
            VALUES (:pk, :issue_date, :doc_no, :basis, :subject, :description, :url, :source_html)
            ON CONFLICT(pk) DO UPDATE SET
                issue_date=excluded.issue_date,
                doc_no=excluded.doc_no,
                basis=excluded.basis,
                subject=excluded.subject,
                description=excluded.description,
                url=excluded.url,
                source_html=excluded.source_html
        """, rec)
        if before: updated += 1
        else: inserted += 1

    con.execute("CREATE INDEX IF NOT EXISTS idx_v2_pk ON explain_letters_v2(pk)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_v2_doc_no ON explain_letters_v2(doc_no)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_v2_issue_date ON explain_letters_v2(issue_date)")
    con.execute(VIEW_CN)
    con.commit()
    con.close()

    print(f"v2 migrate done. inserted={inserted}, updated={updated}")
    print("You can SELECT from view 'explain_letters_cn' to see Chinese column names.")

if __name__ == "__main__":
    main()
