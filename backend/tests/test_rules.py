import json
import os
import sys

os.environ["MOCK_AWS"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import analyzer  # noqa: E402
import app  # noqa: E402
import rules  # noqa: E402

with open(os.path.join(ROOT, "..", "samples", "samples.json"), encoding="utf-8") as fh:
    SAMPLES = json.load(fh)["samples"]


def test_samples_risk_levels():
    for s in SAMPLES:
        out = analyzer.analyze({"text": s["text"], "mode": s.get("mode", "check"), "lang": "en"})
        assert out["risk"] == s["expected_risk"], (s["id"], out["risk"], [f["title"] for f in out["flags"]])


def test_upi_not_valid_flag():
    r = rules.analyze_text("pay to abc.traders@ybl now")
    assert any(f.id == "upi_not_valid" for f in r.flags)


def test_valid_upi_not_flagged():
    r = rules.analyze_text("pay to zerodha.brk@validhdfc")
    assert not any(f.id == "upi_not_valid" for f in r.flags)


def test_lookalike_domain():
    r = rules.analyze_text("login at https://zerodha-vip.top/login")
    assert any(f.id == "lookalike_domain" for f in r.flags)
    r2 = rules.analyze_text("login at https://kite.zerodha.com")
    assert not any(f.id in ("lookalike_domain", "unknown_link") for f in r2.flags)


def test_email_not_upi():
    r = rules.analyze_text("mail me at someone@gmail.com")
    assert r.entities["upi_ids"] == []


def test_stage_for_withdrawal_tax():
    s = next(x for x in SAMPLES if x["id"] == "withdrawal_tax")
    out = analyzer.analyze({"text": s["text"]})
    assert out["scam"]["current"] == 6


def test_paid_mode_complaint_prefilled():
    s = next(x for x in SAMPLES if x["id"] == "already_paid")
    out = analyzer.analyze({"text": s["text"], "mode": "paid"})
    c = out["complaint"]["text"]
    assert "432198765432" in c and "shreeganesh.traders@ybl" in c
    assert out["actions"][0].startswith("Call 1930")


def test_reg_number_unverified_when_registry_empty():
    out = analyzer.analyze({"text": "We are SEBI registered INH000099999, guaranteed returns"})
    assert out["registry"][0]["status"] in ("unverified", "not_found")


def test_handler_routes():
    ev = {"requestContext": {"http": {"method": "POST"}}, "rawPath": "/api/analyze",
          "body": json.dumps({"text": "guaranteed 5% daily return, pay to x.y@paytm"})}
    r = app.handler(ev)
    assert r["statusCode"] == 200 and json.loads(r["body"])["risk"] == "high"
    r = app.handler({"requestContext": {"http": {"method": "POST"}}, "rawPath": "/api/analyze", "body": "{}"})
    assert r["statusCode"] == 400
    r = app.handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": "/api/health"})
    assert r["statusCode"] == 200


def test_negated_guarantee_not_flagged():
    r = rules.analyze_text("Past performance does not guarantee future returns.")
    assert not any(f.id == "guaranteed_returns" for f in r.flags)


def test_personal_upi_without_investment_context_ok():
    r = rules.analyze_text("Shall we split the dinner bill? Send 850 to priya.k@okicici")
    assert r.flags == []


def test_labelled_set_no_regressions():
    import csv
    rows = list(csv.DictReader(open(os.path.join(ROOT, "..", "eval", "labelled.csv"), encoding="utf-8")))
    for row in rows:
        out = analyzer.analyze({"text": row["text"], "mode": row["mode"]})
        flagged = out["risk"] in ("high", "medium")
        assert flagged == (row["label"] == "scam"), (row["id"], out["risk"])


def test_dont_worry_guarantee_still_flagged():
    r = rules.analyze_text("Don't worry, guaranteed returns for all members")
    assert any(f.id == "guaranteed_returns" for f in r.flags)


def test_hindi_screenshot_text_flagged():
    txt = "सर, आपका प्रॉफिट ₹14,85,000 है। पैसे निकालने के लिए पहले 20% टैक्स ₹2,97,000 जमा करना होगा। A/c No 50100234567891 IFSC HDFC0001234"
    out = analyzer.analyze({"text": txt})
    assert out["risk"] == "high"


def test_unreadable_screenshot_is_not_reported_safe():
    import base64
    img = base64.b64encode(b"\x89PNG fake").decode()
    ev = {"requestContext": {"http": {"method": "POST"}}, "rawPath": "/api/analyze",
          "body": json.dumps({"text": "please check", "images": [{"data": img, "mime": "image/png"}]})}
    r = app.handler(ev)
    assert r["statusCode"] == 422
