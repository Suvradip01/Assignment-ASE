"""Deterministic text quality checks used without an API key."""

import re

JUNK_ADDRESSES = {"", ".", "..", "xyz", "asdf", "home", "call me", "test", "na", "n/a"}
FAKE_NAMES = {"asdf", "test", "test order", "customer", "unknown", "xxx", "abc"}


def address_score(address: object) -> float:
    """Estimate address completeness on a 0 to 1 scale."""
    text = str(address or "").strip().lower()
    if text in JUNK_ADDRESSES or len(text) < 8:
        return 0.05
    score = (
        0.35
        + 0.25 * bool(re.search(r"\d", text))
        + 0.20
        * bool(
            re.search(
                r"\b(road|street|area|near|opp|landmark|nagar|colony|chowk|mandir|market)\b",
                text,
            )
        )
    )
    return min(1.0, float(score) + min(len(text), 80) / 400)


def is_fake_name(name: object) -> bool:
    """Flag common test and placeholder names."""
    value = re.sub(r"\s+", " ", str(name or "").strip().lower())
    return (
        value in FAKE_NAMES or len(value) < 2 or bool(re.fullmatch(r"(.)\1{2,}", value))
    )


def address_language(address: object) -> str:
    """Return hinglish for Devanagari or common Hindi address terms."""
    value = str(address or "").lower()
    return (
        "hinglish"
        if re.search(r"[\u0900-\u097f]|\b(ke saamne|paas|gali|ghar|mohalla)\b", value)
        else "en"
    )
