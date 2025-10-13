# export_cn.py
import csv, sqlite3
from pathlib import Path

DB_PATH = "explain_letters.sqlite"
OUT = "exports/explain_letters_cn.csv"

def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.execute("""
        SELECT "ID","發文日期","發文字號","根據","主旨","說明","來源網址"
        FROM explain_letters_cn
        ORDER BY "發文日期" DESC
    """)
    rows = cur.fetchall()
    headers = ["ID","發文日期","發文字號","根據","主旨","說明","來源網址"]
    Path("exports").mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print("Wrote:", OUT)

if __name__ == "__main__":
    main()
