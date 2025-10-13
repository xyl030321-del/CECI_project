# run.py
import argparse
import json
from pathlib import Path

from crawler import make_driver, perform_search, scrape_first_n_details
from parse import parse_detail_v2
from db import get_conn, upsert_letter_v2
from config import DB_PATH, JSONL_EXPORT  # JSONL_EXPORT -> normalized export path

CN_JSONL_EXPORT = "exports/explain_letters_cn.jsonl"  # Chinese-headers export

def run(keyword: str, headless: bool = False, limit: int = 50):
    """
    1) open search page, submit keyword
    2) click through first N 檢視 items (unique by pk)
    3) parse v2 fields (ID/發文日期/發文字號/根據/主旨/說明)
    4) upsert into explain_letters_v2
    5) export JSONL (normalized + Chinese headers)
    """
    driver = make_driver(headless=headless)
    conn = get_conn(DB_PATH)

    cn_records = []     # for Chinese-headers export
    norm_records = []   # for normalized export

    try:
        perform_search(driver, keyword)
        items = scrape_first_n_details(driver, n=limit)

        for item in items:
            # v2 parse returns (fields_cn, normalized)
            fields_cn, rec = parse_detail_v2(item["html"], item["url"], item["pk"])

            # write into v2 table
            upsert_letter_v2(conn, rec)

            # collect for exports
            cn_records.append({
                "ID": rec["pk"],
                "發文日期": rec["issue_date"],
                "發文字號": rec["doc_no"],
                "根據": rec["basis"],
                "主旨": rec["subject"],
                "說明": rec["description"],
                "來源網址": rec["url"],
            })
            norm_records.append(rec)

        # ensure exports/ exists
        Path("exports").mkdir(parents=True, exist_ok=True)

        # normalized JSONL (keys: pk, issue_date, doc_no, basis, subject, description, url, source_html)
        with open(JSONL_EXPORT, "w", encoding="utf-8") as f:
            for r in norm_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        # Chinese-headers JSONL (ID/發文日期/發文字號/根據/主旨/說明/來源網址)
        with open(CN_JSONL_EXPORT, "w", encoding="utf-8") as f:
            for r in cn_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        print(f"Saved {len(norm_records)} records to DB (explain_letters_v2)")
        print(f"Exported normalized JSONL -> {JSONL_EXPORT}")
        print(f"Exported Chinese-headers JSONL -> {CN_JSONL_EXPORT}")

    finally:
        driver.quit()

def main():
    ap = argparse.ArgumentParser(description="Scrape PRMS explain letters to SQLite (v2) and JSONL exports")
    ap.add_argument("--kw", "--keyword", dest="keyword", default="履約", help="search keyword (default: 履約)")
    ap.add_argument("--limit", "-n", type=int, default=50, help="how many cases to fetch (default: 50)")
    ap.add_argument("--headless", action="store_true", help="run Chrome in headless mode")
    args = ap.parse_args()

    run(keyword=args.keyword, headless=args.headless, limit=args.limit)

if __name__ == "__main__":
    main()
