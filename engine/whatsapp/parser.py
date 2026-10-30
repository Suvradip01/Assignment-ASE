"""Rule-first parsing for WhatsApp replies."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Intent:
    """Parsed customer intent."""

    value: str
    needs_llm: bool = False


YES = {
    "yes",
    "y",
    "yeah",
    "ok",
    "okay",
    "confirm",
    "confirmed",
    "haan",
    "ha",
    "han",
    "haa",
    "theek hai",
    "thik hai",
    "kar do",
    "bhej do",
    "1",
}
NO = {
    "no",
    "n",
    "nahi",
    "nahin",
    "nhi",
    "cancel kardo",
    "mat bhejo",
    "nahi chahiye",
    "2",
}
YES_EMOJI = {"👍", "👍🏻", "✅", "👌"}
NO_EMOJI = {"👎", "👎🏻", "❌"}


def _normalize_reply(text: str) -> tuple[str, set[str]]:
    """Normalize punctuation and return the normalized text and its tokens."""
    value = re.sub(r"[^\w\s]", " ", str(text).lower(), flags=re.UNICODE).replace(
        "_", " "
    )
    value = " ".join(value.split())
    return value, set(value.split())


def _prepaid_intent(tokens: set[str], value: str, yes: bool, no: bool) -> Intent | None:
    """Interpret replies while a prepaid payment choice is pending."""
    if "paid" in tokens:
        return Intent("PAID")
    if "keep cod" in value:
        return Intent("KEEP_COD")
    if "pay online" in value or "pay" in tokens:
        return Intent("PAY")
    if "cancel" in tokens:
        return Intent("CANCEL")
    if yes:
        return Intent("PAY")
    if no:
        return Intent("KEEP_COD")
    return None


def _address_intent(value: str, state: str) -> Intent | None:
    """Recognize a likely full address supplied during address confirmation."""
    location_terms = ["road", "area", "nagar", "near", "gali", "colony"]
    has_address_detail = re.search(r"\d", value) or any(
        term in value for term in location_terms
    )
    if state == "AWAITING_ADDRESS" and len(value) >= 10 and has_address_detail:
        return Intent("ADDRESS")
    return None


def parse_reply(text: str, state: str) -> Intent:
    """Parse button payloads and common English/Hinglish replies."""
    raw = str(text).strip()
    if raw in YES_EMOJI:
        return Intent("YES")
    if raw in NO_EMOJI:
        return Intent("NO")
    value, tokens = _normalize_reply(raw)
    stop_phrases = ["stop", "unsubscribe", "band karo messages"]
    if any(phrase in value for phrase in stop_phrases):
        return Intent("STOP")
    if "no problem" in value:
        return Intent("UNCLEAR", True)
    yes = bool(tokens & YES) or value in YES
    no = bool(tokens & NO) or value in NO
    if yes and no:
        return Intent("UNCLEAR", True)
    if state in {"AWAITING_PREPAID_CHOICE", "AWAITING_PAYMENT"}:
        prepaid_result = _prepaid_intent(tokens, value, yes, no)
        if prepaid_result:
            return prepaid_result
    if yes:
        return Intent("YES")
    if no or "cancel" in tokens:
        return Intent("NO")
    address_result = _address_intent(value, state)
    if address_result:
        return address_result
    return Intent("UNCLEAR", True)
