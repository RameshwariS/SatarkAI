"""Build backend/src/sebi_registry.csv from SEBI's Recognised Intermediaries pages.

How to use:
  1. Open https://www.sebi.gov.in/intermediaries.html and pick
     "Investment Adviser", then "Research Analyst", then "Stock Brokers".
  2. Save each result page (Ctrl+S, "Web page, HTML only") into a folder,
     e.g. sebi_pages/. Save every page of results.
  3. Run:  python scripts/build_registry.py sebi_pages/
It pulls every "Registration No." (INA/INH/INZ + 9 digits) and the name shown
above it, and writes backend/src/sebi_registry.csv.
"""
import csv
import html
import os
import re
import sys

REG_RE = re.compile(r"(IN[AHZ]\d{9})")
NAME_RE = re.compile(r"Name\s*:?\s*(.+?)\s*(?:Registration\s*No|Reg\.?\s*No|Email|Telephone|Address|$)", re.I)
CATS = {"INA": "Investment Adviser", "INH": "Research Analyst", "INZ": "Stock Broker"}


def text_of(path):
    raw = open(path, encoding="utf-8", errors="ignore").read()
    raw = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<[^>]+>", "\n", raw)
    return html.unescape(re.sub(r"[ \t]+", " ", raw))


def main(folder):
    rows = {}
    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith((".html", ".htm")):
            continue
        lines = [ln.strip() for ln in text_of(os.path.join(folder, fn)).splitlines() if ln.strip()]
        last_name = ""
        for i, ln in enumerate(lines):
            if ln.lower().startswith("name"):
                m = NAME_RE.search(ln)
                cand = m.group(1).strip(" :") if m else ""
                if not cand and i + 1 < len(lines):
                    cand = lines[i + 1].strip(" :")
                if cand:
                    last_name = cand
            for reg in REG_RE.findall(ln):
                rows.setdefault(reg, (last_name, CATS[reg[:3]]))
    out = os.path.join(os.path.dirname(__file__), "..", "backend", "src", "sebi_registry.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["reg_no", "name", "category"])
        for reg, (name, cat) in sorted(rows.items()):
            w.writerow([reg, name, cat])
    print(f"Wrote {len(rows)} registrations to {os.path.abspath(out)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
