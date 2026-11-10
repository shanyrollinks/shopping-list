#!/usr/bin/env python3
"""כלי עזר לסקיל shopping-list.

aggregate RECEIPT.json [RECEIPT.json ...]   -> מדפיס JSON של מוצרים מאוחדים (שם, כמה קניות, מחיר, כמות טיפוסית, רמה)
render CURATED.json OUT.html               -> ממלא את template.html ומוציא את דף הרשימה
"""
import json, sys, statistics, pathlib, re, hashlib

HERE = pathlib.Path(__file__).resolve().parent.parent


def norm(name):
    return re.sub(r"\s+", " ", str(name)).strip()


def tier_for(share):
    if share >= 0.85: return 1
    if share >= 0.6: return 2
    if share >= 0.4: return 3
    return 4


def aggregate(paths):
    receipts = [json.load(open(p, encoding="utf-8")) for p in paths]
    n = len(receipts)
    seen = {}
    for r in receipts:
        for ln in r.get("lines", []):
            if ln.get("discount") or ln.get("total", 0) <= 0 or not ln.get("name"):
                continue
            name = norm(ln["name"])
            qty = ln.get("qty") or 1
            total = ln.get("total") or 0
            unit_price = ln.get("unit_price") or (total / qty if qty else total)
            seen.setdefault(name, []).append((id(r), qty, unit_price, bool(ln.get("weighted"))))
    out = []
    for name, rows in seen.items():
        weeks = len({r[0] for r in rows})
        weighted = sum(1 for r in rows if r[3]) > len(rows) / 2
        by_receipt = {}
        for rid, q, p, w in rows:
            by_receipt[rid] = by_receipt.get(rid, 0) + q
        out.append({
            "name": name,
            "weeks": weeks,
            "of": n,
            "tier": tier_for(weeks / n) if n > 1 else 2,
            "price": round(statistics.median(r[2] for r in rows), 2),
            "unit": 'ק"ג' if weighted else "יח'",
            "qty": round(statistics.median(by_receipt.values()), 2),
        })
    out.sort(key=lambda x: (-x["weeks"], x["name"]))
    return out


def render(curated_path, out_path):
    c = json.load(open(curated_path, encoding="utf-8"))
    secs = c["sections"]
    raw, prices, seen_names = [], {}, set()
    for it in c["items"]:
        s = it["s"]
        if not (0 <= s < len(secs)):
            sys.exit("מחלקה לא קיימת עבור: " + it["name"])
        if it["name"] in seen_names:
            sys.exit("שם כפול: " + it["name"])
        seen_names.add(it["name"])
        # מזהה קבוע שנגזר מהשם, כדי שסימונים ישארו במקומם גם אחרי עדכון הרשימה
        iid = "n-" + hashlib.sha1(norm(it["name"]).encode("utf-8")).hexdigest()[:8]
        raw.append([s, it["name"], it.get("note", ""), it.get("tier", 2), iid])
        if it.get("price"):
            prices[it["name"]] = [it["price"], it.get("unit", "יח'"), it.get("qty", 1)]
    # סדר לפי מחלקה, ובתוכה לפי רמה
    raw.sort(key=lambda r: (r[0], r[3]))
    html = (HERE / "template.html").read_text(encoding="utf-8")
    dump = lambda o: json.dumps(o, ensure_ascii=False)
    html = html.replace("/*__SECTIONS__*/", dump(secs)).replace("/*__RAW__*/", dump(raw)).replace("/*__PRICES__*/", dump(prices))
    html = html.replace("__SUB__", c["sub"]).replace("__HINT__", c["hint"])
    pathlib.Path(out_path).write_text(html, encoding="utf-8")
    print("נכתב", out_path, "|", len(raw), "מוצרים,", len(prices), "עם מחיר")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "aggregate":
        print(json.dumps(aggregate(sys.argv[2:]), ensure_ascii=False, indent=1))
    elif len(sys.argv) == 4 and sys.argv[1] == "render":
        render(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
