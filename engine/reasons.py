"""Template-based explanations for deterministic decisions."""

from typing import Any


def build_reason(decision: Any, facts: dict[str, Any]) -> str:
    """Build a compact plain-English reason from known order facts."""
    reasons = []
    priority = [
        ("override", "policy rule"),
        ("prior_rto", "past returns"),
        ("name_fake", "name looks incomplete"),
        ("address_junk_rule", "address needs checking"),
        ("pincode_history", "pincode delivery history"),
        ("pin_state_mismatch", "pincode and state do not match"),
        ("is_first_time", "first order, so acquisition cost is protected"),
        ("phone_valid", "phone number needs checking"),
        ("high_value", "higher order value"),
    ]
    for key, label in priority:
        value = facts.get(key)
        if value:
            if key == "prior_rto":
                reasons.append(f"{value} past returns")
            elif key == "pincode_history":
                reasons.append(str(value))
            elif key == "phone_valid":
                reasons.append(label)
            else:
                reasons.append(label)
        if len(reasons) == 3:
            break
    if not reasons:
        reasons = ["risk falls in this action's configured band"]
    line = {
        "SHIP": "Shipping as-is has no intervention cost.",
        "CONFIRM": f"Estimated WhatsApp message cost: ₹{decision.est_msg_cost:.0f}.",
        "NUDGE": f"Estimated prepaid discount: ₹{decision.discount_inr:.0f}; message cost: ₹{decision.est_msg_cost:.0f}.",
        "HOLD": f"Estimated return cost avoided: ₹{decision.est_saved:.0f}; estimated cost if a genuine order is held: ₹{decision.est_lost:.0f}.",
    }.get(decision.action, "Order needs review.")
    return f"{decision.action}: {decision.risk:.0%} chance of return. Why: {', '.join(reasons)}. {line}"
