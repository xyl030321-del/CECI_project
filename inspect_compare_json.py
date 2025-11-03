import json, os, textwrap
p = r"pcc_data\data\contracts\compare_result.json"
assert os.path.exists(p), f"File not found: {p}"

with open(p, "r", encoding="utf-8") as f:
    data = json.load(f)

print("\n=== Top-level type ===")
print(type(data).__name__)

def preview(obj, indent=0, maxlen=200):
    pad = "  " * indent
    if isinstance(obj, dict):
        for k, v in list(obj.items())[:10]:
            print(f"{pad}- {k}: {type(v).__name__}")
    elif isinstance(obj, list):
        print(f"{pad}[list length={len(obj)}]")
        if obj:
            print(f"{pad}first item keys:")
            if isinstance(obj[0], dict):
                for k in list(obj[0].keys())[:20]:
                    print(f"{pad}- {k}")
            else:
                print(f"{pad}- (first item is {type(obj[0]).__name__})")

print("\n=== Preview ===")
preview(data)

# If it's a list of clause results, show first item details (truncated)
def show_first(d):
    if isinstance(d, list) and d and isinstance(d[0], dict):
        first = d[0]
        print("\n=== First item (truncated fields) ===")
        for k, v in first.items():
            s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
            s = s.replace("\n"," ")[:300]
            print(f"- {k}: {s}")
    elif isinstance(d, dict):
        print("\n=== Dict keys sample ===")
        for k, v in list(d.items())[:10]:
            print(f"- {k}: {type(v).__name__}")

show_first(data)
print("\nDone.")