#!/usr/bin/env python3
"""כלי עזר לסקיל shopping-list.

aggregate [--out ITEMS.json] RECEIPT.json [RECEIPT.json ...]
                                           -> מוצרים מאוחדים (שם, כמה קניות, מחיר, כמות טיפוסית, רמה).
                                              אפשר לכתוב receipt-*.json (הכוכבית נפתחת כאן, גם בווינדוס).
                                              בלי --out התוצאה מודפסת למסך
render CURATED.json OUT.html               -> ממלא את template.html ומוציא את דף הרשימה
"""
import json, sys, statistics, pathlib, re, hashlib, glob, html as htmllib

# קונסולות ישנות (בעיקר בווינדוס) לא מוגדרות ל-UTF-8, ועברית קורסת בהן
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = pathlib.Path(__file__).resolve().parent.parent


def die(msg):
    sys.stderr.write(msg + "\n")
    sys.exit(1)


def norm(name):
    return re.sub(r"\s+", " ", str(name)).strip()


def num(value):
    """ממיר ערך למספר. מחזיר None אם אי אפשר."""
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ".").strip())
    except ValueError:
        return None


def load(path):
    path = str(pathlib.Path(path).expanduser())
    try:
        return json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        die("לא נמצא הקובץ: %s" % path)
    except json.JSONDecodeError as e:
        die("הקובץ %s לא תקין (שורה %s). צריך לתקן אותו ולהריץ שוב." % (path, e.lineno))


def tier_for(share):
    if share >= 0.85: return 1
    if share >= 0.6: return 2
    if share >= 0.4: return 3
    return 4


def expand(args):
    """פותח כוכביות לבד (ב-cmd ובפאוורשל הן לא נפתחות) ומסיר כפילויות."""
    paths = []
    for a in args:
        a = str(pathlib.Path(a).expanduser())
        found = sorted(glob.glob(a)) if any(c in a for c in "*?[") else [a]
        paths.extend(found or [a])
    seen, out = set(), []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def aggregate(paths):
    paths = expand(paths)
    receipts = [load(p) for p in paths]
    n = len(receipts)
    if n < 3:
        sys.stderr.write("שימו לב: יש רק %d קבלות. עם פחות מ-3 קבלות אי אפשר לדעת מה קונים כל שבוע, והרמות לא מדויקות.\n" % n)
    seen = {}
    for path, r in zip(paths, receipts):
        for ln in r.get("lines", []) if isinstance(r, dict) else []:
            name = norm(ln.get("name", ""))
            total = num(ln.get("total"))
            if ln.get("discount") or not name or (total is not None and total < 0):
                continue
            qty = num(ln.get("qty")) or 1
            price = num(ln.get("unit_price"))
            if price is None and total is not None and qty:
                price = total / qty
            if price is not None and price <= 0:
                price = None
            seen.setdefault(name, []).append((path, qty, price, bool(ln.get("weighted"))))
    out = []
    for name, rows in seen.items():
        weeks = len({r[0] for r in rows})
        weighted = sum(1 for r in rows if r[3]) > len(rows) / 2
        by_receipt = {}
        for rid, q, p, w in rows:
            by_receipt[rid] = by_receipt.get(rid, 0) + q
        prices = [r[2] for r in rows if r[2] is not None]
        out.append({
            "name": name,
            "weeks": weeks,
            "of": n,
            "tier": tier_for(weeks / n) if n > 1 else 2,
            "price": round(statistics.median(prices), 2) if prices else None,
            "unit": 'ק"ג' if weighted else "יח'",
            "qty": round(statistics.median(by_receipt.values()), 2),
        })
    out.sort(key=lambda x: (-x["weeks"], x["name"]))
    return out


def js_dump(obj):
    """JSON בטוח להטמעה בתוך תגית script."""
    s = json.dumps(obj, ensure_ascii=False)
    return s.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def render(curated_path, out_path):
    c = load(curated_path)
    for key in ("sections", "items", "sub", "hint"):
        if key not in c:
            die("בקובץ המסודר חסר השדה: %s" % key)
    secs = c["sections"]
    raw, prices, seen_names = [], {}, {}
    for it in c["items"]:
        name = norm(it.get("name", ""))
        if not name:
            die("יש מוצר בלי שם.")
        s = it.get("s")
        if not isinstance(s, int) or not (0 <= s < len(secs)):
            die("מחלקה לא קיימת עבור המוצר: " + name)
        if name in seen_names:
            die('שם כפול: "%s". צריך לאחד או לשנות שם לאחד מהם.' % name)
        seen_names[name] = True
        # מזהה קבוע שנגזר מהשם, כדי שסימונים ישארו במקומם גם אחרי עדכון הרשימה
        iid = "n-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
        raw.append([s, name, norm(it.get("note", "")), it.get("tier", 2), iid])
        price = num(it.get("price"))
        if price and price > 0:
            prices[name] = [price, it.get("unit", "יח'"), num(it.get("qty")) or 1]
    raw.sort(key=lambda r: (r[0], r[3]))
    values = {
        "/*__SECTIONS__*/": js_dump([norm(x) for x in secs]),
        "/*__RAW__*/": js_dump(raw),
        "/*__PRICES__*/": js_dump(prices),
        "__SUB__": htmllib.escape(str(c["sub"])),
        "__HINT__": htmllib.escape(str(c["hint"])),
    }
    template = (HERE / "template.html").read_text(encoding="utf-8")
    # החלפה בפסקה אחת, כדי שטקסט בתוך השדות לא יוחלף בטעות
    pattern = re.compile("|".join(re.escape(k) for k in values))
    html = pattern.sub(lambda m: values[m.group(0)], template)
    pathlib.Path(out_path).write_text(html, encoding="utf-8")
    print("נכתב", out_path, "|", len(raw), "מוצרים,", len(prices), "עם מחיר")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if len(argv) >= 2 and argv[0] == "aggregate":
        rest = argv[1:]
        out_path = None
        if rest[0] == "--out":
            if len(rest) < 3:
                die("אחרי --out צריך שם קובץ, ואחריו הקבלות.")
            out_path, rest = rest[1], rest[2:]
        text = json.dumps(aggregate(rest), ensure_ascii=False, indent=1)
        if out_path:
            pathlib.Path(out_path).expanduser().write_text(text, encoding="utf-8")
            print("נכתב", out_path)
        else:
            print(text)
    elif len(argv) == 3 and argv[0] == "render":
        render(str(pathlib.Path(argv[1]).expanduser()), str(pathlib.Path(argv[2]).expanduser()))
    else:
        sys.exit(__doc__)
