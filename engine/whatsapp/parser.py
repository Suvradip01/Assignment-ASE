"""Rule-first parsing for WhatsApp replies."""
import re
from dataclasses import dataclass

@dataclass(frozen=True)
class Intent:
    """Parsed customer intent."""
    value: str
    needs_llm: bool = False

YES={"yes","y","yeah","ok","okay","confirm","confirmed","haan","ha","han","haa","theek hai","thik hai","kar do","bhej do","1","👍"}
NO={"no","n","nahi","nahin","nhi","cancel kardo","mat bhejo","nahi chahiye","2","👎"}

def parse_reply(text: str, state: str) -> Intent:
    """Parse button payloads and common English/Hinglish replies."""
    value=re.sub(r"[^\w\s]", " ", str(text).lower(), flags=re.UNICODE).replace("_", " "); value=" ".join(value.split())
    if any(x in value for x in ["stop","unsubscribe","band karo messages"]): return Intent("STOP")
    if "no problem" in value: return Intent("UNCLEAR",True)
    tokens=set(value.split()); yes=bool(tokens & YES) or value in YES; no=bool(tokens & NO) or value in NO
    if yes and no: return Intent("UNCLEAR",True)
    if state in {"AWAITING_PREPAID_CHOICE","AWAITING_PAYMENT"}:
        if "paid" in tokens: return Intent("PAID")
        if "keep cod" in value: return Intent("KEEP_COD")
        if "pay online" in value or "pay" in tokens: return Intent("PAY")
        if "cancel" in tokens: return Intent("CANCEL")
        if yes: return Intent("PAY")
        if no: return Intent("KEEP_COD")
    if yes: return Intent("YES")
    if no or "cancel" in tokens: return Intent("NO")
    if state=="AWAITING_ADDRESS" and len(value)>=10 and (re.search(r"\d",value) or any(w in value for w in ["road","area","nagar","near","gali","colony"])): return Intent("ADDRESS")
    return Intent("UNCLEAR",True)
