"""Check that the LIVE site works end to end, including every AWS service.

  python scripts/smoke_test.py https://dxxxxxxxx.cloudfront.net

Run it after every deploy, and on the morning of Demo Day.
Uses only the Python standard library.
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def call(base, path, body=None):
    req = urllib.request.Request(base.rstrip("/") + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read()
            try:
                data = json.loads(raw)
            except ValueError:
                data = {"_html": raw[:200].decode(errors="ignore")}
            return r.status, data, time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:300]}, time.time() - t0


def main(base):
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {name}{'  -> ' + detail if detail else ''}")

    st, _, _ = call(base, "/")
    check("Website loads (S3 + CloudFront)", st == 200, f"HTTP {st}")

    st, d, _ = call(base, "/api/health")
    check("API reachable (API Gateway + Lambda)", st == 200 and d.get("ok"), json.dumps(d))
    check("Not running in mock mode", st == 200 and not d.get("mock"))

    text = ("Download our institutional trading app https://motilal-vip-trade.top/app.apk. "
            "Pay to shreeganesh.traders@ybl. IPO allotment 100% guaranteed.")
    st, d, sec = call(base, "/api/analyze", {"text": text, "lang": "hi"})
    check("Analyze returns HIGH risk for a scam", st == 200 and d.get("risk") == "high", f"{d.get('risk')} in {sec:.1f}s")
    check("Bedrock used (AI model)", d.get("ai_used") is True, "; ".join(d.get("notes", [])) or "")
    check("Translate used (summary is in Hindi)", any("ऀ" <= ch <= "ॿ" for ch in d.get("summary", "")))
    check("Response under 15 seconds", sec < 15, f"{sec:.1f}s")

    shot = os.path.join(ROOT, "samples", "screenshots", "2_payment_request.png")
    if os.path.exists(shot):
        img = base64.b64encode(open(shot, "rb").read()).decode()
        st, d, sec = call(base, "/api/analyze", {"images": [{"data": img, "mime": "image/png"}], "lang": "en"})
        check("Screenshot check works (Textract + Bedrock)", st == 200 and d.get("risk") == "high"
              and "shreeganesh.traders@ybl" in d.get("entities", {}).get("upi_ids", []), f"{d.get('risk')} in {sec:.1f}s")

    st, d, _ = call(base, "/api/speak", {"text": "Yeh dhokha lagta hai. Paise mat bhejiye.", "lang": "hi"})
    check("Audio works (Polly)", st == 200 and len(d.get("audio", "")) > 1000)

    st, d, _ = call(base, "/api/trends")
    check("Trends work (DynamoDB)", st == 200 and "by_scam" in d, f"{d.get('total_checks')} checks this week")

    print("\nALL GOOD" if ok else "\nSome checks failed. See NEXT_STEPS.md > 'If something fails'.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
