"""Deterministic red-flag engine.

Runs on the text pulled from the user's message or screenshots. It does not
need any AWS service, so it still works if Bedrock is slow or unavailable, and
every flag points to the exact words that triggered it (useful for the judges'
"how do you know?" question).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse

# Official broker / app-store domains. Links to these are fine; links that
# *look like* these but are different are a strong red flag.
OFFICIAL_DOMAINS = {
    "play.google.com": "Google Play Store",
    "apps.apple.com": "Apple App Store",
    "zerodha.com": "Zerodha",
    "groww.in": "Groww",
    "angelone.in": "Angel One",
    "upstox.com": "Upstox",
    "icicidirect.com": "ICICI Direct",
    "hdfcsec.com": "HDFC Securities",
    "kotaksecurities.com": "Kotak Securities",
    "motilaloswal.com": "Motilal Oswal",
    "5paisa.com": "5paisa",
    "dhan.co": "Dhan",
    "paytmmoney.com": "Paytm Money",
    "sharekhan.com": "Sharekhan",
    "sbisecurities.in": "SBI Securities",
    "nseindia.com": "NSE",
    "bseindia.com": "BSE",
    "sebi.gov.in": "SEBI",
    # banks, payment apps and market infrastructure people use legitimately
    "hdfcbank.com": "HDFC Bank", "icicibank.com": "ICICI Bank", "onlinesbi.sbi": "SBI", "sbi.co.in": "SBI",
    "axisbank.com": "Axis Bank", "kotak.com": "Kotak Mahindra Bank", "pnbindia.in": "PNB", "bankofbaroda.in": "Bank of Baroda",
    "idfcfirstbank.com": "IDFC First Bank", "indusind.com": "IndusInd Bank", "yesbank.in": "Yes Bank", "canarabank.com": "Canara Bank",
    "paytm.com": "Paytm", "phonepe.com": "PhonePe", "pay.google.com": "Google Pay",
    "rbi.org.in": "RBI", "npci.org.in": "NPCI", "amfiindia.com": "AMFI", "mfcentral.com": "MF Central",
    "camsonline.com": "CAMS", "kfintech.com": "KFintech", "cdslindia.com": "CDSL", "nsdl.co.in": "NSDL",
    "cybercrime.gov.in": "Cyber Crime Portal", "sancharsaathi.gov.in": "Sanchar Saathi", "incometax.gov.in": "Income Tax Dept",
}
# Global fund names scammers borrow ("BlackRock India VIP club"). Indian brokers are
# covered by lookalike_brand(), which also catches spelling tricks.
BRAND_WORDS = {"blackrock", "goldman", "goldmansachs", "jpmorgan", "morganstanley", "nomura", "vanguard", "citadel", "fidelity"}

# Common consumer UPI handles (personal accounts). Payments for "investment"
# to these go to an individual, not to a SEBI-registered intermediary.
PERSONAL_UPI_HANDLES = {
    "ybl", "ibl", "axl", "paytm", "ptyes", "ptaxis", "pthdfc", "ptsbi",
    "okaxis", "okhdfcbank", "okicici", "oksbi", "apl", "upi", "axisbank",
    "icici", "sbi", "hdfcbank", "kotak", "fbl", "freecharge", "jupiteraxis",
    "slice", "naviaxis", "yapl", "waicici", "wahdfcbank", "wasbi", "waaxis",
}

UPI_RE = re.compile(r"\b([a-zA-Z0-9][a-zA-Z0-9.\-_]{1,255}@[a-zA-Z][a-zA-Z0-9]{1,63})\b")
URL_RE = re.compile(r"\b((?:https?://|www\.)[^\s<>\"']+|[a-z0-9\-]+\.(?:apk|com|in|net|org|io|app|vip|top|xyz|cc|co|club|site|online|pro)(?:/[^\s<>\"']*)?)", re.I)
AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr)\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.I)
UTR_RE = re.compile(r"\b(?:utr|ref(?:erence)?|txn|transaction)\s*(?:no\.?|id|#|number)?\s*[:\-]?\s*([A-Z0-9]{10,22})\b", re.I)
IFSC_RE = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
ACCOUNT_RE = re.compile(r"\b(?:a/?c|account)\s*(?:no\.?|number)?\s*[:\-]?\s*([0-9]{9,18})\b", re.I)
SEBI_REG_RE = re.compile(r"\b(IN[AHZ][0-9]{9})\b", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\-\s]?)?([6-9][0-9]{9})(?!\d)")
PERCENT_RETURN_RE = re.compile(
    r"(\d{1,4}(?:\.\d+)?)\s?%\s*(?:return|profit|returns|gain|मुनाफा|रिटर्न|नफा|परतावा)?\s*(?:per|a|in|every|last|this|प्रति|हर)?\s*"
    r"(day|daily|week|weekly|month|monthly|दिन|रोज|हफ्ते|महीने|आठवडा|महिना|\d+\s*days?)",
    re.I,
)


@dataclass
class Flag:
    id: str
    title: str
    why: str
    evidence: str
    weight: int
    stage_hint: int | None = None  # which stage of stock_tips_group it suggests
    scam_hint: str | None = None
    match: str = ""  # the exact words that triggered it (for highlighting)


@dataclass
class RuleResult:
    flags: list[Flag] = field(default_factory=list)
    entities: dict = field(default_factory=dict)
    score: int = 0

    def to_dict(self):
        return {
            "flags": [asdict(f) for f in self.flags],
            "entities": self.entities,
            "score": self.score,
        }


# (id, title, why, weight, stage_hint, scam_hint, patterns)
KEYWORD_RULES = [
    ("guaranteed_returns", "Guaranteed or 'no-risk' returns",
     "No real investment can guarantee profit. SEBI-registered advisers are not allowed to promise assured returns.",
     30, 1, None,
     [r"guarant(?:eed|ee)", r"assured\s+returns?", r"fixed\s+returns?", r"no\s+loss", r"zero\s+risk", r"100\s?%\s+(?:profit|safe|sure)",
      r"risk[\s-]?free", r"गारंटी", r"पक्का\s+मुनाफा", r"बिना\s+रिस्क", r"हमखास", r"खात्रीशीर"]),
    ("withdrawal_fee", "Asked to pay before you can withdraw",
     "Real brokers deduct any tax or charges from your balance. Being told to pay first to 'unlock' or withdraw is the classic final stage of a fake trading app.",
     45, 6, None,
     [r"withdraw\w*\s+(?:tax|fee|charge)", r"(?:tax|fee|charges?|margin)\s+(?:to|before|for)\s+withdraw", r"unlock\s+(?:fee|charge|amount)",
      r"unfreeze", r"pay\s+(?:the\s+)?(?:income\s+)?tax\s+(?:first|before)", r"service\s+fee\s+(?:to|before)", r"clear\s+(?:the\s+)?dues",
      r"निकासी\s+(?:शुल्क|टैक्स)", r"पैसे\s+निकालने\s+के\s+लिए", r"पैसे\s+काढण्यासाठी"]),
    ("institutional_account", "'Institutional', 'OTC', 'block deal' or 'VIP' account",
     "Ordinary investors cannot get institutional quotas or discounted OTC shares through a WhatsApp group. This wording is used to move victims onto fake apps.",
     30, 3, None,
     [r"institution(?:al)?\s+(?:account|quota|trading|seats?)", r"\bOTC\b", r"block\s+deals?", r"VIP\s+(?:account|group|channel|seat)",
      r"pre[\s-]?IPO", r"discount(?:ed)?\s+shares"]),
    ("ipo_allotment_promise", "Promised IPO allotment",
     "IPO allotment is decided by a lottery by the registrar. Nobody can promise you allotment.",
     30, 5, "fake_ipo_institutional",
     [r"(?:sure|guarante\w*|confirm\w*|100\s?%)\s+(?:IPO\s+)?allotment", r"allotment\s+(?:is\s+)?(?:\d+\s?%\s+)?(?:guarante\w*|confirm\w*|sure)", r"IPO\s+(?:quota|allotment)\s+(?:for|in)\s+(?:you|our)"]),
    ("mentor_group", "Stock-tips group run by a 'professor', 'mentor' or 'assistant'",
     "Scam groups use a fake expert plus an 'assistant' who adds you and handles payments, often claiming to be from a famous broker or fund.",
     15, 2, "stock_tips_group",
     [r"\bprofessor\b", r"\bmentor\b", r"\b(?:teaching\s+)?assistant\b", r"stock\s+(?:tips?|learning|class(?:es)?)", r"trading\s+class",
      r"whatsapp\s+group", r"telegram\s+(?:group|channel)", r"\bdaily\s+(?:tips|session|class)"]),
    ("fake_profit_screenshots", "Members posting profit screenshots",
     "Most 'members' in these groups are fake accounts run by the scammers, posting made-up profits to create trust.",
     10, 2, "stock_tips_group",
     [r"profit\s+screenshots?", r"(?:members|students)\s+(?:earned|made|profit)", r"today'?s\s+profit"]),
    ("app_outside_store", "App shared as a file or link, not from an official store",
     "Fake trading apps are shared as APK files or web links. A real broker's app is on Play Store/App Store under the broker's own name.",
     30, 3, "stock_tips_group",
     [r"\.apk\b", r"download\s+(?:the\s+|our\s+)?app\s+(?:from|using|via)\s+(?:this\s+)?link", r"install\s+(?:from\s+)?(?:this\s+)?link",
      r"not\s+(?:available\s+)?on\s+play\s?store"]),
    ("urgency", "Pressure to act fast",
     "Urgency stops you from checking with family or a real adviser.",
     10, None, None,
     [r"today\s+only", r"limited\s+(?:seats|slots|time|offer)", r"last\s+chance", r"hurry", r"within\s+\d+\s+(?:minutes|hours)",
      r"account\s+will\s+be\s+(?:frozen|blocked|closed)", r"जल्दी", r"आज\s+ही", r"लवकर"]),
    ("secrecy", "Asked to keep it secret",
     "Scammers tell victims not to tell family or bank staff, because they would stop the payment.",
     20, None, None,
     [r"(?:don'?t|do\s+not)\s+(?:tell|share|inform)", r"keep\s+(?:it\s+)?(?:secret|confidential)", r"किसी\s+को\s+मत\s+बताना"]),
    ("in_app_loan", "Loan or 'credit' offered inside the app",
     "Fake apps show a 'loan' so you feel you owe money and must deposit more.",
     30, 5, "stock_tips_group",
     [r"(?:loan|credit|margin)\s+(?:of\s+)?(?:₹|rs)?\s?[0-9,]+\s+(?:approved|granted|credited)", r"repay\s+(?:the\s+)?(?:loan|credit)", r"negative\s+balance"]),
    ("task_job", "Paid 'tasks' that need you to pay first",
     "Earning money for likes or reviews and then 'prepaying' for bigger tasks is a well-known task scam.",
     35, None, "task_job_scam",
     [r"prepaid\s+task", r"merchant\s+task", r"(?:like|subscribe)\s+(?:youtube\s+)?videos?\s+(?:and|to)\s+earn", r"rate\s+(?:hotels|products)\s+(?:and|to)\s+earn",
      r"part[\s-]?time\s+(?:job|work).{0,40}(?:earn|daily)"]),
    ("crypto_forex", "Crypto, USDT or forex trading platform",
     "Many forex/crypto platforms promoted on social media are not authorised in India. The RBI keeps an alert list of unauthorised forex platforms.",
     20, None, "crypto_forex",
     [r"\bUSDT\b", r"\bforex\b", r"\bMT[45]\b", r"binary\s+options?", r"crypto\s+(?:trading|mining|arbitrage)", r"double\s+your\s+(?:money|investment)"]),
    ("referral_income", "Income for adding others",
     "Returns that depend on recruiting new people is how Ponzi schemes work.",
     25, None, "ponzi_app",
     [r"referral\s+(?:income|bonus|commission)", r"level\s+income", r"team\s+income", r"refer\s+(?:\d+\s+)?friends?\s+(?:and|to)\s+earn"]),
    ("fools_checkers", "Message tries to fool safety checks",
     "It contains text aimed at apps or AI checkers (like 'verified safe' or 'ignore previous instructions'). Genuine messages never need this.",
     30, None, None,
     [r"ignore\s+(?:all\s+)?(?:previous|above|prior)\s+(?:instructions|rules)", r"(?:AI|assistant|scanner|checker|antivirus)\s*[:,]?\s*(?:this|the)\s+(?:message|link|app)\s+is\s+(?:safe|genuine|verified)",
      r"verified\s+safe\s+by", r"system\s*(?:message|note)\s*:", r"<\s*/?\s*(?:system|untrusted_input)\s*>"]),
    ("claims_sebi", "Claims to be SEBI-registered",
     "Scammers often show a real SEBI number that belongs to someone else, or a made-up one. Check it yourself on SEBI's site.",
     5, None, None,
     [r"sebi[\s-]?(?:registered|approved|certified|licensed)"]),
]


# negation directly before the match, same clause ("does not guarantee", "no assured returns");
# punctuation breaks it, so "Don't worry, guaranteed returns" is still flagged
NEGATION_RE = re.compile(r"(?:\bnot|\bno|\bnever|\bcannot|\bcan't|n't|\bnahi|नहीं|नाही)\s+(?:\w+\s+)?$", re.I)
INVESTMENT_CONTEXT_RE = re.compile(
    r"invest|trad(?:e|ing)|profit|deposit|returns?\b|stock|share|IPO|tips|crypto|forex|withdraw|broker|demat|"
    r"portfolio|mutual\s+fund|scheme|plan|task|bonus|earn|निवेश|मुनाफा|शेयर|गुंतवणूक|नफा", re.I)


def _find(patterns, text):
    for p in patterns:
        for m in re.finditer(p, text, re.I):
            # "does not guarantee", "no fixed returns" etc. are the opposite of a red flag
            if NEGATION_RE.search(text[max(0, m.start() - 30):m.start()]):
                continue
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            return text[start:end].replace("\n", " ").strip(), m.group(0)
    return None


def _domain(url: str) -> str:
    u = url if url.lower().startswith(("http://", "https://")) else "http://" + url
    host = (urlparse(u).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


BRAND_NAMES = {  # official name -> how people know it
    "zerodha": "Zerodha", "groww": "Groww", "angelone": "Angel One", "upstox": "Upstox", "icicidirect": "ICICI Direct",
    "hdfcsec": "HDFC Securities", "kotaksecurities": "Kotak Securities", "motilaloswal": "Motilal Oswal",
    "5paisa": "5paisa", "paytmmoney": "Paytm Money", "sharekhan": "Sharekhan", "sbisecurities": "SBI Securities",
    "nseindia": "NSE", "bseindia": "BSE", "sebi": "SEBI", "dhan": "Dhan",
}
_LEET = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "$": "s", "@": "a"})


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def lookalike_brand(host: str) -> str | None:
    """'zer0dha-vip.in', 'upst0x.co', 'grovv.in' -> the brand being imitated."""
    labels = host.split(".")
    if len(labels) < 2:
        return None
    for part in labels[:-1]:
        for chunk in [part] + part.split("-"):
            norm = chunk.translate(_LEET).replace("-", "").replace("vv", "w").replace("rn", "m")
            for key, name in BRAND_NAMES.items():
                key_norm = key.translate(_LEET)
                if len(norm) < 4:
                    continue
                if norm == key_norm:  # exact name on an unofficial domain (zer0dha.in, sebi-verify.in)
                    return name
                if len(key_norm) >= 6 and key_norm in norm:  # brand inside a longer word (zerodhatrade)
                    return name
                # small typos of long names only, never shorter words ('paisa' is not '5paisa')
                if (len(key_norm) >= 6 and 0 <= len(norm) - len(key_norm) <= 2
                        and _edit_distance(norm, key_norm) <= (1 if len(key_norm) < 8 else 2)):
                    return name
    return None


def _is_official(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in OFFICIAL_DOMAINS)


def extract_entities(text: str) -> dict:
    upis = sorted({m.group(1) for m in UPI_RE.finditer(text) if "." not in m.group(1).split("@")[1]})
    # drop things that are actually emails
    upis = [u for u in upis if not re.search(r"@(gmail|yahoo|outlook|hotmail|rediffmail)$", u, re.I)]
    urls = sorted({m.group(1).rstrip(".,)") for m in URL_RE.finditer(text)})
    urls = [u for u in urls if "@" not in u]
    amounts = []
    for m in AMOUNT_RE.finditer(text):
        try:
            amounts.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return {
        "upi_ids": upis,
        "urls": urls,
        "amounts": amounts,
        "utrs": sorted({m.group(1) for m in UTR_RE.finditer(text)}),
        "ifsc": sorted({m.group(1) for m in IFSC_RE.finditer(text)}),
        "accounts": sorted({m.group(1) for m in ACCOUNT_RE.finditer(text)}),
        "sebi_reg_numbers": sorted({m.group(1).upper() for m in SEBI_REG_RE.finditer(text)}),
        "phones": sorted({m.group(1) for m in PHONE_RE.finditer(text)}),
    }


def analyze_text(text: str) -> RuleResult:
    res = RuleResult()
    text = text or ""
    for rid, title, why, weight, stage, scam, patterns in KEYWORD_RULES:
        found = _find(patterns, text)
        if found:
            ev, matched = found
            res.flags.append(Flag(rid, title, why, ev, weight, stage, scam, matched))

    # Unrealistic % returns
    for m in PERCENT_RETURN_RE.finditer(text):
        pct = float(m.group(1))
        period = m.group(2).lower()
        daily = any(k in period for k in ("day", "daily", "दिन", "रोज"))
        weekly = any(k in period for k in ("week", "हफ्ते", "आठवडा"))
        monthly = any(k in period for k in ("month", "महीने", "महिना"))
        too_high = (daily and pct >= 0.5) or (weekly and pct >= 3) or (monthly and pct >= 5) or (
            not (daily or weekly or monthly) and pct >= 10)
        if too_high:
            res.flags.append(Flag(
                "unrealistic_returns", "Unrealistic return promised",
                f"{pct:g}% {period} is far above what any genuine investment gives. For comparison, a bank FD gives about 6–7% a year.",
                m.group(0), 30, 1, None))
            break

    ents = extract_entities(text)
    res.entities = ents

    # Payment destination checks: only when the message is about investing/earning.
    # (Paying a friend for dinner on UPI is not a red flag.)
    investment_context = bool(res.flags) or bool(INVESTMENT_CONTEXT_RE.search(text))
    for upi in (ents["upi_ids"] if investment_context else []):
        handle = upi.split("@", 1)[1].lower()
        if handle.startswith("valid"):
            continue
        personal = handle in PERSONAL_UPI_HANDLES
        res.flags.append(Flag(
            "upi_not_valid", "Payment UPI ID is not a SEBI '@valid' ID",
            ("Since Oct 2025, SEBI-registered brokers and advisers collect money through UPI IDs ending in '@valid…'. "
             + ("This looks like a personal UPI ID. " if personal else "")
             + "Do not send investment money here. Verify it on SEBI Check first."),
            upi, 35, 4, None))
        break  # one flag is enough
    if investment_context and (ents["accounts"] or ents["ifsc"]):
        res.flags.append(Flag(
            "bank_transfer_request", "Asked to transfer to a bank account directly",
            "Investment money should go only to your own broker account through its official app. Check any account number on SEBI Check before paying.",
            (ents["accounts"] + ents["ifsc"])[0], 20, 4, None))

    # Link checks
    for url in ents["urls"]:
        host = _domain(url)
        if not host:
            continue
        if url.lower().endswith(".apk") or host.endswith(".apk"):
            if not any(f.id == "app_outside_store" for f in res.flags):
                res.flags.append(Flag("app_outside_store", "App shared as an APK file",
                                      "Real broker apps come from Play Store/App Store. APK files can be fake apps or malware.",
                                      url, 30, 3, "stock_tips_group"))
            continue
        if _is_official(host):
            continue
        brand = lookalike_brand(host) or next((b for b in BRAND_WORDS if b in host.replace("-", "")), None)
        if brand:
            res.flags.append(Flag(
                "lookalike_domain", "Website pretends to be a known brand",
                f"'{host}' looks like '{brand}' but is not the official website we know for it. Fake trading sites copy real names with small changes.",
                url, 40, 3, "stock_tips_group"))
        else:
            res.flags.append(Flag(
                "unknown_link", "Unknown trading/investment link",
                f"'{host}' is not a known broker or official app store. Check that the platform is a SEBI-registered broker before depositing.",
                url, 10, 3, None))

    for f in res.flags:
        if not f.match:
            f.match = f.evidence

    # De-duplicate by id, keep first
    seen, uniq = set(), []
    for f in res.flags:
        if f.id not in seen:
            seen.add(f.id)
            uniq.append(f)
    res.flags = uniq
    res.score = min(100, sum(f.weight for f in res.flags))
    return res


def risk_level(score: int) -> str:
    if score >= 60:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def guess_scam_and_stage(flags: list[Flag]) -> tuple[str | None, int | None]:
    """Pick the scam type by weighted votes (ties go to the stock-tips group,
    the most common pattern) and the furthest stage the evidence shows.
    Stage hints are written on the 7-stage stock-group scale; they are mapped
    onto shorter playbooks later."""
    votes: dict[str, int] = {}
    for f in flags:
        if f.scam_hint:
            votes[f.scam_hint] = votes.get(f.scam_hint, 0) + f.weight
    if votes:
        top = max(votes.values())
        best = [k for k, v in votes.items() if v == top]
        scam = "stock_tips_group" if "stock_tips_group" in best else best[0]
    else:
        scam = "stock_tips_group" if flags else None
    stages = [f.stage_hint for f in flags if f.stage_hint]
    stage = max(stages) if stages else None
    return scam, stage


def map_stage(stage7: int | None, n_stages: int) -> int | None:
    """Map a stage on the 7-stage scale onto a playbook with n_stages."""
    if not stage7:
        return None
    if n_stages >= 7:
        return stage7
    table = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 3}
    return min(n_stages, table.get(stage7, 1))
