"""AWS Lambda entry point (API Gateway HTTP API, payload v2)."""
from __future__ import annotations

import base64
import json
import traceback

import analyzer
import aws

MAX_BODY = 5_500_000  # Lambda sync payload limit is 6 MB


def _resp(status: int, body: dict):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "content-type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def handler(event, context=None):
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")
    if path.startswith("/api"):
        path = path[4:] or "/"
    if method == "OPTIONS":
        return _resp(204, {})

    try:
        raw = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode("utf-8")
        if len(raw) > MAX_BODY:
            return _resp(413, {"error": "Screenshots are too large. Please send up to 3 smaller images."})
        body = json.loads(raw) if method == "POST" else {}

        if path == "/health":
            return _resp(200, {"ok": True, "model": aws.MODEL_ID, "mock": aws.MOCK})
        if path == "/analyze" and method == "POST":
            if not (body.get("text") or body.get("images")):
                return _resp(400, {"error": "Paste a message or add a screenshot."})
            try:
                return _resp(200, analyzer.analyze(body))
            except analyzer.UnreadableInput as e:
                return _resp(422, {"error": str(e)})
        if path == "/speak" and method == "POST":
            try:
                audio = aws.speak(body.get("text", ""), body.get("lang", "en"))
            except ValueError as e:
                return _resp(400, {"error": str(e)})
            return _resp(200, {"audio": audio, "format": "mp3"})
        if path == "/trends":
            return _resp(200, analyzer.trends())
        return _resp(404, {"error": "Not found"})
    except json.JSONDecodeError:
        return _resp(400, {"error": "Bad request"})
    except Exception:
        traceback.print_exc()  # goes to CloudWatch Logs
        return _resp(500, {"error": "Something went wrong. Please try again."})
