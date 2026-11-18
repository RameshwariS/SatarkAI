"""Lookup of SEBI registration numbers against a local copy of SEBI's
Recognised Intermediaries list (investment advisers, research analysts,
stock brokers).

The copy lives in sebi_registry.csv (columns: reg_no,name,category).
Build it with scripts/build_registry.py from pages saved from sebi.gov.in.
If the file is empty we say so honestly and point to SEBI's own tools.
"""
from __future__ import annotations

import csv
import os
import re

_REG = None
CATEGORY_BY_PREFIX = {"INA": "Investment Adviser", "INH": "Research Analyst", "INZ": "Stock Broker"}


def _load():
    global _REG
    if _REG is not None:
        return _REG
    _REG = {}
    path = os.path.join(os.path.dirname(__file__), "sebi_registry.csv")
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                reg = (row.get("reg_no") or "").strip().upper()
                if reg:
                    _REG[reg] = {"name": (row.get("name") or "").strip(), "category": (row.get("category") or "").strip()}
    return _REG


def registry_size() -> int:
    return len(_load())


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower())


def check_numbers(reg_numbers: list[str], text: str) -> list[dict]:
    reg = _load()
    out = []
    for n in reg_numbers:
        n = n.upper()
        item = {"reg_no": n, "category": CATEGORY_BY_PREFIX.get(n[:3], "Unknown")}
        if not reg:
            item.update(status="unverified",
                        message="Our copy of the SEBI list is not loaded. Search this number at sebi.gov.in/intermediaries.html before trusting it.")
        elif n not in reg:
            item.update(status="not_found",
                        message="This number is not in SEBI's list of registered intermediaries in our copy. Treat it as fake unless sebi.gov.in/intermediaries.html shows it.")
        else:
            name = reg[n]["name"]
            mentioned = _norm(name).split()[:2]
            name_in_chat = bool(mentioned) and all(w in _norm(text) for w in mentioned)
            item.update(status="found", registered_name=name,
                        message=(f"Registered to '{name}'. "
                                 + ("The name in the chat matches." if name_in_chat else
                                    "The chat does not use this name, so a scammer may be borrowing a real number. Contact the adviser only through details on SEBI's website.")))
        out.append(item)
    return out
