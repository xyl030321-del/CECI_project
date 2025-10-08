# -*- coding: utf-8 -*-
from pathlib import Path
OUT = Path("out"); OUT.mkdir(exist_ok=True, parents=True)

# try both names
cands = ["inputs\Contract01.docx"]
path = next((Path(n) for n in cands if Path(n).exists()), None)
if not path:
    raise SystemExit("❌ Put Contract01.docx (or Contract01.docx.docx) next to this file.")

import docx2txt
text = docx2txt.process(str(path)) or ""
pages = text.split("\f")
print(f"Found {len(pages)} page chunks via docx2txt for {path.name}")

# dump first two pages to inspect
for i, pg in enumerate(pages[:2]):
    (OUT / f"diag_contract01_page{i}.txt").write_text(pg, encoding="utf-8")
print("Wrote:", OUT / "diag_contract01_page0.txt", "and", OUT / "diag_contract01_page1.txt")
