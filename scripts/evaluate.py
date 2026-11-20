"""Measure how well SatarkAI works on a labelled set of messages.

  # rules only, on your laptop
  MOCK_AWS=1 python scripts/evaluate.py eval/labelled.csv
  # the full app (rules + Textract/Bedrock), against your live URL
  python scripts/evaluate.py eval/labelled.csv --url https://dxxxx.cloudfront.net

CSV columns: id,label,mode,source,text
  label  = scam | genuine
  mode   = check | paid
  source = where the message came from (synthetic, news, family, volunteer, ...)

A message counts as "flagged" when the app says high OR medium risk.
Writes eval/report.md. Quote only numbers measured on REAL messages
(source != synthetic) in your submission.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_local(row):
    sys.path.insert(0, os.path.join(ROOT, "backend", "src"))
    import analyzer  # noqa: WPS433
    return analyzer.analyze({"text": row["text"], "mode": row["mode"] or "check", "lang": "en"})


def run_remote(row, url):
    req = urllib.request.Request(
        url.rstrip("/") + "/api/analyze",
        data=json.dumps({"text": row["text"], "mode": row["mode"] or "check", "lang": "en"}).encode(),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read())


def pct(a, b):
    return f"{100 * a / b:.0f}% ({a}/{b})" if b else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--url", help="live site URL; omit to run locally")
    ap.add_argument("--out", default=os.path.join(ROOT, "eval", "report.md"))
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8")))
    results, times = [], []
    for row in rows:
        t0 = time.time()
        try:
            out = run_remote(row, args.url) if args.url else run_local(row)
        except Exception as e:  # keep going, record the failure
            out = {"risk": "error", "flags": [], "scam": None, "ai_used": False, "notes": [str(e)]}
        times.append(time.time() - t0)
        flagged = out["risk"] in ("high", "medium")
        results.append({**row, "risk": out["risk"], "flagged": flagged,
                        "scam_type": (out.get("scam") or {}).get("id", ""),
                        "stage": (out.get("scam") or {}).get("current", ""),
                        "ai_used": out.get("ai_used", False),
                        "n_flags": len(out.get("flags", []))})
        print(f"{row['id']:>5} {row['label']:>8} -> {out['risk']:>6}  {'OK' if flagged == (row['label'] == 'scam') else 'MISS'}")

    def summary(subset, name):
        scams = [r for r in subset if r["label"] == "scam"]
        genuine = [r for r in subset if r["label"] == "genuine"]
        caught = sum(r["flagged"] for r in scams)
        high = sum(r["risk"] == "high" for r in scams)
        false_alarm = sum(r["flagged"] for r in genuine)
        return (f"### {name}\n\n| Measure | Result |\n| --- | --- |\n"
                f"| Scam messages flagged (high or medium) | {pct(caught, len(scams))} |\n"
                f"| Scam messages rated high | {pct(high, len(scams))} |\n"
                f"| Genuine messages wrongly flagged | {pct(false_alarm, len(genuine))} |\n")

    real = [r for r in results if r["source"].strip().lower() != "synthetic"]
    synth = [r for r in results if r["source"].strip().lower() == "synthetic"]
    lines = [
        "# SatarkAI evaluation report", "",
        f"Run on {time.strftime('%Y-%m-%d %H:%M')} against {'live site ' + args.url if args.url else 'local code'}. "
        f"AI model used on {sum(r['ai_used'] for r in results)}/{len(results)} messages. "
        f"Average time per check: {sum(times) / max(1, len(times)):.1f}s.", "",
    ]
    if real:
        lines += [summary(real, f"Real messages ({len(real)}): quote these numbers")]
    else:
        lines += ["**No real messages yet.** Add real, anonymised messages (source = news / family / volunteer) "
                  "before quoting any accuracy number.", ""]
    if synth:
        lines += [summary(synth, f"Synthetic test messages ({len(synth)}): for checking the code only")]
    misses = [r for r in results if r["flagged"] != (r["label"] == "scam")]
    lines += ["### Misses", ""]
    lines += ([f"- `{r['id']}` ({r['label']}, {r['source']}): app said **{r['risk']}**: {r['text'][:120]}…" for r in misses]
              or ["None."])
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    open(args.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"\nReport written to {args.out}")


if __name__ == "__main__":
    main()
