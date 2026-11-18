"""Thin wrappers around the AWS services we use. boto3 is imported lazily so
the rule engine and tests run on a laptop without AWS credentials.

Set MOCK_AWS=1 to skip every AWS call (local demo / tests).
"""
from __future__ import annotations

import base64
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

MOCK = os.environ.get("MOCK_AWS") == "1"
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
TABLE = os.environ.get("CHECKS_TABLE", "")

_clients = {}


def client(name):
    if name not in _clients:
        import boto3  # noqa: WPS433 (lazy import on purpose)
        _clients[name] = boto3.client(name)
    return _clients[name]


# ---------- Textract: read text from screenshots ----------
def ocr_image(img_bytes: bytes) -> str:
    """Textract DetectDocumentText. Good at English, numbers, UPI IDs, URLs,
    amounts and transaction IDs, which are what the rule engine needs.
    Hindi/Marathi text in screenshots is read by the Bedrock model instead."""
    if MOCK:
        return ""
    resp = client("textract").detect_document_text(Document={"Bytes": img_bytes})
    lines = [b["Text"] for b in resp.get("Blocks", []) if b.get("BlockType") == "LINE"]
    return "\n".join(lines)


# ---------- Bedrock: understand the scam ----------
def ask_model(system: str, user_text: str, images: list[tuple[bytes, str]]) -> str:
    if MOCK:
        raise RuntimeError("mock mode: model disabled")
    content = [{"text": user_text}]
    for data, fmt in images[:3]:
        content.append({"image": {"format": fmt, "source": {"bytes": data}}})
    resp = client("bedrock-runtime").converse(
        modelId=MODEL_ID,
        system=[{"text": system}],
        messages=[{"role": "user", "content": content}],
        inferenceConfig={"maxTokens": 1800, "temperature": 0.1},
    )
    return resp["output"]["message"]["content"][0]["text"]


def parse_json(text: str) -> dict:
    s = text.strip()
    if "```" in s:
        s = s.split("```")[1]
        if s.lower().startswith("json"):
            s = s[4:]
    start, end = s.find("{"), s.rfind("}")
    return json.loads(s[start:end + 1])


# ---------- Translate: explain in the user's language ----------
@lru_cache(maxsize=4096)
def _translate_one(text: str, lang: str) -> str:
    if MOCK or not text or lang == "en":
        return text
    resp = client("translate").translate_text(Text=text, SourceLanguageCode="en", TargetLanguageCode=lang)
    return resp["TranslatedText"]


def translate_many(texts: list[str], lang: str) -> list[str]:
    if MOCK or lang == "en":
        return texts
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(lambda t: _translate_one(t, lang), texts))


# ---------- Polly: read the result aloud ----------
POLLY_LANG = {"hi": "hi-IN", "en": "en-IN"}


def speak(text: str, lang: str) -> str:
    """Returns base64 MP3. Polly's Indian voice (Kajal) covers Hindi and Indian English."""
    if lang not in POLLY_LANG:
        raise ValueError("Audio is available in Hindi and English for now.")
    if MOCK:
        return ""
    resp = client("polly").synthesize_speech(
        Text=text[:2900], OutputFormat="mp3", VoiceId="Kajal", Engine="neural", LanguageCode=POLLY_LANG[lang])
    return base64.b64encode(resp["AudioStream"].read()).decode()


# ---------- DynamoDB: anonymous counts for the weekly trend ----------
def record_check(scam_id: str | None, risk: str, stage: int | None, city: str | None):
    """Stores NO message text, images, UPI IDs or phone numbers. Only the
    scam type, risk level, stage and an optional city the user typed."""
    if MOCK or not TABLE:
        return
    now = int(time.time())
    client("dynamodb").put_item(TableName=TABLE, Item={
        "pk": {"S": "CHECK"},
        "sk": {"S": f"{now}#{uuid.uuid4().hex[:8]}"},
        "scam_id": {"S": scam_id or "none"},
        "risk": {"S": risk},
        "stage": {"N": str(stage or 0)},
        "city": {"S": (city or "").strip().title()[:40] or "Unknown"},
        "ttl": {"N": str(now + 90 * 86400)},
    })


def recent_checks(days: int = 7) -> list[dict]:
    if MOCK or not TABLE:
        return []
    since = int(time.time()) - days * 86400
    items, kwargs = [], dict(
        TableName=TABLE,
        KeyConditionExpression="pk = :p AND sk >= :s",
        ExpressionAttributeValues={":p": {"S": "CHECK"}, ":s": {"S": str(since)}},
    )
    while True:
        resp = client("dynamodb").query(**kwargs)
        items += resp.get("Items", [])
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return [{"scam_id": i["scam_id"]["S"], "risk": i["risk"]["S"], "city": i["city"]["S"]} for i in items]
