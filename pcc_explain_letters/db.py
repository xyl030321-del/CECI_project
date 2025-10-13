import sqlite3
from pathlib import Path

def get_conn(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS explain_letters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pk TEXT UNIQUE,                 -- pkPrmsRuleContent
        doc_no TEXT,                    -- 發文字號
        subject TEXT,                   -- 主旨/標題
        issue_date TEXT,                -- 發文日期 (民國或西元原樣保存)
        category TEXT,                  -- 類別/法規 (若可擷取)
        content TEXT,                   -- 內容(全文)
        url TEXT,                       -- 詳文頁 URL
        source_html TEXT                -- 原始HTML (可做後處理/重抽取)
    )
    """)
    return conn

def upsert_letter(conn, rec: dict):
    conn.execute("""
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
    conn.commit()

def upsert_letter_v2(conn, rec: dict):
    conn.execute("""
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
    conn.commit()

