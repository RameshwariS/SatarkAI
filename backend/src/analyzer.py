"""Main pipeline: screenshots/text -> OCR -> rules + Bedrock -> merged verdict
-> translated explanation (+ complaint draft if the user already paid)."""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone, timedelta

import aws
import registry
import rules

HERE = os.path.dirname(__file__)
with open(os.path.join(HERE, "playbook.json"), encoding="utf-8") as fh:
    PLAYBOOK = json.load(fh)
SCAMS = {s["id"]: s for s in PLAYBOOK["scams"]}
IST = timezone(timedelta(hours=5, minutes=30))

class UnreadableInput(Exception):
    """Raised when screenshots were sent but no text could be read from them."""


SUPPORTED_LANGS = {"en": "English", "hi": "हिंदी", "mr": "मराठी", "gu": "ગુજરાતી", "ta": "தமிழ்",
                   "te": "తెలుగు", "kn": "ಕನ್ನಡ", "bn": "বাংলা", "ml": "മലയാളം", "pa": "ਪੰਜਾਬੀ"}

SYSTEM_PROMPT = """You are Nivesh Kavach, an assistant that helps ordinary Indians check whether an investment offer, trading group or trading app is a scam.
You will get: text the user pasted, text read from their screenshots by OCR, the screenshots themselves (which may be in Hindi, Marathi or other Indian languages), and red flags already found by a rule engine.

Known scam playbook (use these ids):
{playbook}

Rules:
- Judge only from what is shown. Do not invent facts. If it is not about money/investment, say so.
- Real SEBI-registered brokers never run WhatsApp/Telegram tip groups that ask you to pay a personal UPI ID, never guarantee returns, never ask for tax/fees before a withdrawal.
- Write for a non-expert, short and plain English (it will be translated).
- Return ONLY a JSON object, no other text, with this shape:
{{
  "is_investment_related": true/false,
  "scam_id": one of [{ids}, "none", "unclear"],
  "stage": integer stage number within that scam (or 0),
  "risk": "high" | "medium" | "low",
  "summary": "2-3 sentences: what is going on and why",
  "extra_flags": [{{"title": "...", "why": "...", "evidence": "exact words from the input"}}],
  "next_move": "one or two sentences: what the scammer will most likely do next",
  "extracted_text": "all text you can read in the screenshots, in the original language",
  "entities": {{"upi_ids": [], "urls": [], "amounts_paid": [], "utrs": [], "sebi_reg_numbers": [], "platform_name": "", "claimed_company": "", "contact_names": []}}
}}"""


def _playbook_for_prompt() -> str:
    lines = []
    for s in PLAYBOOK["scams"]:
        stages = "; ".join(f"{st['n']}={st['name']}" for st in s["stages"])
        lines.append(f"- {s['id']}: {s['name']}. Stages: {stages}")
    return "\n".join(lines)


def _decode_images(images: list[dict]) -> list[tuple[bytes, str]]:
    out = []
    for img in (images or [])[:3]:
        data = img.get("data", "")
        if "," in data[:100]:
            data = data.split(",", 1)[1]
        raw = base64.b64decode(data)
        mime = (img.get("mime") or "image/jpeg").lower()
        fmt = "png" if "png" in mime else "webp" if "webp" in mime else "jpeg"
        out.append((raw, fmt))
    return out


def _stage_info(scam_id: str | None, stage: int | None):
    scam = SCAMS.get(scam_id or "")
    if not scam:
        return None
    n = max(1, min(stage or 1, len(scam["stages"])))
    return {
        "id": scam["id"], "name": scam["name"], "summary": scam["summary"],
        "current": n,
        "stages": [{"n": st["n"], "name": st["name"]} for st in scam["stages"]],
        "next": scam["stages"][n - 1]["next"],
    }


def analyze(payload: dict) -> dict:
    text = (payload.get("text") or "").strip()
    lang = payload.get("lang") if payload.get("lang") in SUPPORTED_LANGS else "en"
    mode = "paid" if payload.get("mode") == "paid" else "check"
    images = _decode_images(payload.get("images") or [])
    notes = []

    # 1) OCR screenshots with Textract
    ocr_text = ""
    for raw, _ in images:
        try:
            ocr_text += "\n" + aws.ocr_image(raw)
        except Exception as e:  # keep going; the model can still read the image
            notes.append(f"Textract skipped: {type(e).__name__}")

    # 2) Ask Bedrock (with rule-engine hints)
    base_text = f"{text}\n{ocr_text}".strip()
    first_pass = rules.analyze_text(base_text)
    model = None
    try:
        hint = "\n".join(f"- {f.title}: \"{f.evidence}\"" for f in first_pass.flags) or "(none)"
        user_msg = (f"User's mode: {'they ALREADY PAID money' if mode == 'paid' else 'checking before paying'}\n\n"
                    f"Pasted text:\n{text or '(none)'}\n\nOCR text from screenshots:\n{ocr_text.strip() or '(none)'}\n\n"
                    f"Rule-engine red flags:\n{hint}")
        system = SYSTEM_PROMPT.format(playbook=_playbook_for_prompt(), ids=", ".join(f'"{k}"' for k in SCAMS))
        model = aws.parse_json(aws.ask_model(system, user_msg, images))
    except Exception as e:
        notes.append("Demo mode: AI model off, showing rule-based result only." if aws.MOCK else f"AI model unavailable ({type(e).__name__}); showing rule-based result only.")

    # 3) Second rule pass including text the model read (covers Hindi/Marathi screenshots)
    full_text = base_text
    if model and model.get("extracted_text"):
        full_text += "\n" + str(model["extracted_text"])
    rr = rules.analyze_text(full_text)
    if model:
        ents = model.get("entities") or {}
        for k_model, k_rule in (("upi_ids", "upi_ids"), ("urls", "urls"), ("utrs", "utrs"), ("sebi_reg_numbers", "sebi_reg_numbers")):
            for v in ents.get(k_model) or []:
                if v and v not in rr.entities[k_rule]:
                    rr.entities[k_rule].append(v)
        rr.entities["platform_name"] = ents.get("platform_name") or ""
        rr.entities["claimed_company"] = ents.get("claimed_company") or ""
        rr.entities["amounts_paid"] = ents.get("amounts_paid") or []

    # 4) Merge verdicts: safety first, never let the model lower a rule-based HIGH
    flags = [{"title": f.title, "why": f.why, "evidence": f.evidence, "source": "rule"} for f in rr.flags]
    for xf in (model or {}).get("extra_flags") or []:
        if xf.get("title") and all(xf["title"].lower() != f["title"].lower() for f in flags):
            flags.append({"title": xf["title"], "why": xf.get("why", ""), "evidence": xf.get("evidence", ""), "source": "ai"})

    order = {"low": 0, "medium": 1, "high": 2}
    rule_risk = rules.risk_level(rr.score)
    model_risk = (model or {}).get("risk") if (model or {}).get("risk") in order else "low"
    risk = max(rule_risk, model_risk, key=order.get)
    if mode == "paid" and risk == "low" and flags:
        risk = "medium"

    # Never show "low risk" for screenshots we could not read: that would look like a safe verdict.
    read_something = bool(ocr_text.strip()) or bool((model or {}).get("extracted_text"))
    if images and not read_something and risk == "low":
        raise UnreadableInput("We couldn't read your screenshot right now. Please paste the message text instead, or try again.")

    rule_scam, rule_stage = rules.guess_scam_and_stage(rr.flags)
    if (model or {}).get("scam_id") in SCAMS:
        scam_id, stage = model["scam_id"], model.get("stage") or None
    else:
        scam_id = rule_scam
        stage = rules.map_stage(rule_stage, len(SCAMS[scam_id]["stages"])) if scam_id else None
    if mode == "paid" and scam_id in SCAMS:
        stage = max(stage or 0, rules.map_stage(4, len(SCAMS[scam_id]["stages"])))
    stage_info = _stage_info(scam_id, stage) if risk != "low" else None

    if model and model.get("summary"):
        summary = model["summary"]
    elif risk == "high":
        summary = "This shows several signs of a known investment scam. Do not send any more money."
    elif risk == "medium":
        summary = "Some warning signs found. Verify the platform and payment details on SEBI's official tools before paying anything."
    else:
        summary = "We did not find clear scam signs in what you shared. That does not prove it is safe: invest only through a SEBI-registered broker's official app."
    next_move = (model or {}).get("next_move") or (stage_info or {}).get("next", "")

    reg_checks = registry.check_numbers(rr.entities.get("sebi_reg_numbers", []), full_text)

    actions = _actions(risk, mode, rr.entities)
    complaint = _complaint(rr.entities, scam_id, payload) if mode == "paid" else None

    # 5) Translate the human-facing text
    to_tr = [summary, next_move] + [f["title"] for f in flags] + [f["why"] for f in flags] + actions
    if stage_info:
        to_tr += [stage_info["name"]] + [s["name"] for s in stage_info["stages"]]
    try:
        tr = aws.translate_many(to_tr, lang)
    except Exception as e:
        notes.append(f"Translation unavailable ({type(e).__name__}); showing English.")
        tr, lang = to_tr, "en"
    it = iter(tr)
    summary_t, next_t = next(it), next(it)
    for f in flags:
        f["title_t"] = next(it)
    for f in flags:
        f["why_t"] = next(it)
    actions_t = [next(it) for _ in actions]
    if stage_info:
        stage_info["name_t"] = next(it)
        for s in stage_info["stages"]:
            s["name_t"] = next(it)

    try:
        aws.record_check(scam_id if risk != "low" else None, risk, stage, payload.get("city"))
    except Exception as e:
        notes.append(f"Trend logging skipped: {type(e).__name__}")

    return {
        "risk": risk,
        "score": rr.score,
        "lang": lang,
        "mode": mode,
        "summary": summary_t,
        "next_move": next_t,
        "flags": flags,
        "scam": stage_info,
        "entities": {k: v for k, v in rr.entities.items() if k != "phones"},
        "registry": reg_checks,
        "registry_loaded": registry.registry_size() > 0,
        "actions": actions_t,
        "complaint": complaint,
        "ai_used": model is not None,
        "notes": notes,
        "disclaimer": "Nivesh Kavach gives guidance, not a guarantee. Always verify on sebi.gov.in and report fraud at 1930 / cybercrime.gov.in.",
    }


def _actions(risk: str, mode: str, ents: dict) -> list[str]:
    if mode == "paid":
        return list(PLAYBOOK["first_hour_steps"])
    acts = []
    if risk in ("high", "medium"):
        acts.append("Do not send any money or install any app they shared.")
    if ents.get("upi_ids") or ents.get("accounts"):
        acts.append("Check the UPI ID or bank account on SEBI Check (siportal.sebi.gov.in/intermediary/sebi-check or the Saarthi app) before paying. Genuine brokers use UPI IDs ending in '@valid'.")
    acts.append("Invest only through a SEBI-registered broker's official app from Play Store/App Store.")
    if ents.get("sebi_reg_numbers"):
        acts.append("Search the SEBI registration number at sebi.gov.in/intermediaries.html and contact that adviser only using the details SEBI shows.")
    if risk == "high":
        acts.append("Exit the group and report the number on Sanchar Saathi (Chakshu) and the chat on cybercrime.gov.in.")
    acts.append("Talk to a family member before investing. Scammers rely on you deciding alone.")
    return acts


def _complaint(ents: dict, scam_id: str | None, payload: dict) -> dict:
    now = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")
    scam_name = SCAMS.get(scam_id or "", {}).get("name", "Online investment fraud")
    amounts = ents.get("amounts_paid") or ents.get("amounts") or []
    lines = [
        "To: National Cyber Crime Reporting Portal (cybercrime.gov.in) / Cyber Police",
        "Category: Online Financial Fraud > Investment Scam / Trading Scam",
        "",
        f"I want to report an online investment fraud ({scam_name}).",
        "",
        "Platform / group used: " + (ents.get("platform_name") or "[name of WhatsApp/Telegram group or app]"),
        "Company they claimed to be: " + (ents.get("claimed_company") or "[company name]"),
        "Website / app links: " + (", ".join(ents.get("urls") or []) or "[links]"),
        "",
        "Payments made:",
    ]
    utrs = ents.get("utrs") or []
    upis = ents.get("upi_ids") or []
    if amounts or utrs:
        n = max(len(amounts), len(utrs), 1)
        for i in range(n):
            amt = f"₹{amounts[i]:,.0f}" if i < len(amounts) and isinstance(amounts[i], (int, float)) else (str(amounts[i]) if i < len(amounts) else "[amount]")
            utr = utrs[i] if i < len(utrs) else "[UTR / transaction ID]"
            lines.append(f"  {i + 1}. Amount {amt}, UTR {utr}, Date/time [date, time]")
    else:
        lines.append("  1. Amount [₹], UTR [transaction ID], Date/time [date, time]")
    lines += [
        "Paid to UPI ID(s): " + (", ".join(upis) or "[UPI ID]"),
        "Paid to bank account(s): " + (", ".join(ents.get("accounts") or []) or "[account no.]")
        + (" IFSC " + ", ".join(ents["ifsc"]) if ents.get("ifsc") else ""),
        "",
        "What happened (short): [How you were contacted, what they promised, when you realised it was fraud]",
        "",
        "I request that the above transactions be frozen and the money returned. Screenshots of chats and payments are attached.",
        "",
        "Name: [your name]   Mobile: [your number]   Address: [your address]",
        f"Draft prepared on {now} using Nivesh Kavach. Please check every detail before submitting.",
    ]
    return {
        "text": "\n".join(lines),
        "helpline": "1930",
        "portal": "https://cybercrime.gov.in",
        "missing": [p for p in ("[UTR / transaction ID]", "[UPI ID]", "[amount]") if p in "\n".join(lines)],
    }


def trends() -> dict:
    items = aws.recent_checks(7)
    by_scam, by_city = {}, {}
    for i in items:
        if i["risk"] == "low" or i["scam_id"] == "none":
            continue
        by_scam[i["scam_id"]] = by_scam.get(i["scam_id"], 0) + 1
        by_city[i["city"]] = by_city.get(i["city"], 0) + 1
    return {
        "days": 7,
        "total_checks": len(items),
        "by_scam": [{"id": k, "name": SCAMS.get(k, {}).get("name", k), "count": v} for k, v in sorted(by_scam.items(), key=lambda x: -x[1])],
        "by_city": [{"city": k, "count": v} for k, v in sorted(by_city.items(), key=lambda x: -x[1])[:10]],
    }
