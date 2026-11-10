#!/usr/bin/env python3
"""בדיקה מהירה שהסקיל עובד: מריץ את הדוגמה מקצה לקצה. הרצה: python3 tests/run.py"""
import json, pathlib, re, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
SH = str(ROOT / "scripts" / "shopping.py")


def run(*args, expect=0):
    r = subprocess.run([PY, SH, *args], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == expect, "קוד יציאה %s: %s" % (r.returncode, r.stderr)
    return r


def main():
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t)
        items = t / "items.json"
        run("aggregate", "--out", str(items), str(ROOT / "example" / "receipt-*.json"))  # כוכבית נפתחת בסקריפט
        data = json.loads(items.read_text(encoding="utf-8"))
        names = {i["name"] for i in data}
        assert {"עגבניות", "חלב 3%", "לחם אחיד", "ביצים"} <= names, names
        assert "הנחת מבצע" not in names
        curated = {"sections": ["ירקות", "מזווה </script>"], "sub": "<b>דוגמה</b>", "hint": "x",
                   "items": [{"s": 0, "name": i["name"] + " </script>", "tier": i["tier"], "price": i["price"], "unit": i["unit"], "qty": i["qty"]} for i in data]}
        c = t / "curated.json"
        c.write_text(json.dumps(curated, ensure_ascii=False), encoding="utf-8")
        out = t / "out.html"
        run("render", str(c), str(out))
        html = out.read_text(encoding="utf-8")
        assert not re.search(r"__[A-Z]+__", html), "נשארו תבניות לא מולאו"
        assert html.count("</script>") == 1, "מחרוזת </script> בשם שוברת את הדף"
        run("aggregate", str(t / "אין-כזה.json"), expect=1)
    print("הכול עובד")


if __name__ == "__main__":
    main()
