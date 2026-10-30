"""Deterministic action selection and impact estimates."""

from dataclasses import dataclass, field
from typing import Any
import hashlib
import pandas as pd
from engine.economics import (
    discount,
    rto_cost,
    value_at_stake,
    conversion_rate,
    prepaid_rto,
)
from engine.config import config_hash
from engine.reasons import build_reason

REQUIRED_ORDER_FIELDS = [
    "order_id",
    "order_datetime",
    "customer_name",
    "phone",
    "address",
    "city",
    "state",
    "pincode",
    "order_value",
    "num_items",
    "items",
    "customer_prior_orders",
    "customer_prior_rto",
    "utm_source",
]


@dataclass(frozen=True)
class Decision:
    """A scored order decision and its expected impact."""

    order_id: str
    action: str
    risk: float
    reason: str = ""
    discount_inr: float = 0.0
    flow: str | None = None
    flags: list[str] = field(default_factory=list)
    est_saved: float = 0.0
    est_lost: float = 0.0
    est_discount_cost: float = 0.0
    est_msg_cost: float = 0.0
    llm_source: str = "rules"
    model_version: str = "logistic-v1"
    config_hash: str = ""
    control_group: bool = False
    decided_at: str = ""


def _missing_order_field(order: dict[str, Any]) -> str:
    """Return the first missing required field, if one exists."""
    missing = order.get("missing_fields", "")
    if missing:
        return str(missing).split(", ")[0]
    return next(
        (
            field
            for field in REQUIRED_ORDER_FIELDS
            if field not in order
            or order[field] is None
            or pd.isna(order[field])
            or (isinstance(order[field], str) and not order[field].strip())
        ),
        "",
    )


def _early_decision(
    order: dict[str, Any], risk: float, rules: dict[str, Any]
) -> Decision | None:
    """Return a safe decision for invalid values or missing required fields."""
    order_id = str(order.get("order_id", ""))
    order_value = order.get("order_value")
    invalid_value = order_value is not None and not pd.isna(order_value)
    if invalid_value and float(order_value) < rules["min_order_value"]:
        return Decision(
            order_id,
            "HOLD",
            float(risk),
            reason=(
                "HOLD: invalid order value. Why: order value is below the "
                "configured minimum. Holding prevents scoring bad data."
            ),
            flags=["invalid_order_value"],
            config_hash=config_hash(),
        )
    missing_field = _missing_order_field(order)
    if not missing_field:
        return None
    return Decision(
        order_id,
        "CONFIRM",
        float(risk),
        reason=f"Could not assess: missing {missing_field}",
        flow="confirm",
        flags=["missing_required_field"],
        config_hash=config_hash(),
    )


def _base_action(
    order: dict[str, Any], risk: float, cfg: Any, score: float, fake: bool
) -> tuple[str, str | None, list[str]]:
    """Apply blocking rules and configured customer risk bands."""
    rules = cfg["rules"]
    flags: list[str] = []
    first_time = int(order.get("customer_prior_orders", 0) or 0) == 0
    group = "first_time_customer" if first_time else "repeat_customer"
    band = cfg["risk_bands"][group]
    phone = str(order.get("phone", ""))
    pincode = str(order.get("pincode", ""))
    if phone in rules["blocked_phones"] or pincode in rules["blocked_pincodes"]:
        return "HOLD", None, ["manual_block"]
    invalid_details = score < rules["junk_address_below_score"] and (
        fake or int(order.get("phone_valid", 1) or 0) == 0
    )
    if invalid_details:
        return "HOLD", None, ["undeliverable_details"]
    if risk >= band["hold_at_or_above"]:
        return "HOLD", None, flags
    if risk >= band["nudge_from"]:
        return "NUDGE", "nudge", flags
    if risk >= band["ship_below"]:
        return "CONFIRM", "confirm", flags
    return "SHIP", None, flags


def _apply_order_overrides(
    order: dict[str, Any],
    risk: float,
    cfg: Any,
    score: float,
    action: str,
    flow: str | None,
    flags: list[str],
) -> tuple[str, str | None, list[str], float]:
    """Apply address, repeat-returner, and prepaid-discount overrides."""
    rules = cfg["rules"]
    pincode = str(order.get("pincode", ""))
    if action != "HOLD" and score < rules["junk_address_below_score"]:
        if action in {"SHIP", "NUDGE"}:
            action = "CONFIRM"
        flow = "confirm_address"
        flags.append("junk_address")
    is_repeat_returner = (
        int(order.get("customer_prior_rto", 0) or 0)
        >= rules["repeat_returner_min_prior_rto"]
    )
    prepaid_only = pincode in rules["prepaid_only_pincodes"]
    if action != "HOLD" and (is_repeat_returner or prepaid_only):
        if action in {"SHIP", "CONFIRM"}:
            action = "NUDGE"
        if action == "NUDGE":
            flow = "nudge_prepaid_only"
        flags.append("prepaid_only")
    discount_value = 0.0
    if action == "NUDGE":
        discount_value = discount(risk, order, cfg)
        if discount_value == 0:
            action = "CONFIRM"
            flow = "confirm"
            flags.append("discount_not_viable")
    return action, flow, flags, discount_value


def _apply_control_group(
    order: dict[str, Any], cfg: Any, action: str, flow: str | None, flags: list[str]
) -> tuple[str, str | None, list[str]]:
    """Send a stable configured share of intervention orders to SHIP."""
    share = float(cfg["rules"]["control_group_pct"])
    if share <= 0 or action not in {"CONFIRM", "NUDGE", "HOLD"}:
        return action, flow, flags
    digest = hashlib.sha256(str(order.get("order_id", "")).encode()).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if bucket >= share * 100:
        return action, flow, flags
    flags.append(f"would_have_been_{action}")
    return "SHIP", None, flags


def _estimate_impact(
    order: dict[str, Any], risk: float, cfg: Any, action: str, discount_value: float
) -> tuple[float, float, float, float]:
    """Calculate saved, lost, discount, and message cost estimates."""
    order_value = max(1, float(order.get("order_value", 0)))
    conversion = (
        conversion_rate(risk, discount_value / order_value * 100, cfg)
        if action == "NUDGE"
        else 0
    )
    prepaid_risk = prepaid_rto(risk, cfg)
    stake = value_at_stake(order, cfg)
    return_cost = rto_cost(cfg)
    saved = _saved_estimate(action, risk, conversion, prepaid_risk, return_cost, cfg)
    lost = _lost_estimate(action, risk, conversion, stake, cfg)
    discount_cost = conversion * discount_value if action == "NUDGE" else 0
    message_cost = (
        cfg["costs"]["whatsapp_message_cost"] if action in {"CONFIRM", "NUDGE"} else 0
    )
    return saved, lost, discount_cost, message_cost


def _saved_estimate(
    action: str,
    risk: float,
    conversion: float,
    prepaid_risk: float,
    return_cost: float,
    cfg: Any,
) -> float:
    """Estimate avoided return costs for the selected action."""
    if action == "CONFIRM":
        return (
            risk * cfg["assumptions"]["confirm_catches_share_of_returns"] * return_cost
        )
    if action == "HOLD":
        return risk * return_cost
    if action == "NUDGE":
        return conversion * (risk - prepaid_risk) * return_cost
    return 0.0


def _lost_estimate(
    action: str, risk: float, conversion: float, stake: float, cfg: Any
) -> float:
    """Estimate value lost from genuine orders affected by intervention."""
    if action == "CONFIRM":
        share = cfg["assumptions"]["confirm_loses_share_of_genuine"]
    elif action == "HOLD":
        share = 1.0
    elif action == "NUDGE":
        share = cfg["assumptions"]["nudge_annoyed_cancel_share"] * (1 - conversion)
    else:
        share = 0.0
    return (1 - risk) * (share * stake)


def decide(
    order_row: dict[str, Any],
    risk: float,
    cfg: Any,
    text_flags: dict[str, Any] | None = None,
) -> Decision:
    """Apply rule precedence, risk bands, and deterministic impact maths."""
    order = dict(order_row)
    text = text_flags or {}
    early = _early_decision(order, risk, cfg["rules"])
    if early:
        return early
    score = float(text.get("address_score", order.get("address_score", 1)))
    fake = bool(text.get("name_fake", order.get("name_fake", False)))
    action, flow, flags = _base_action(order, risk, cfg, score, fake)
    action, flow, flags, discount_value = _apply_order_overrides(
        order, risk, cfg, score, action, flow, flags
    )
    action, flow, flags = _apply_control_group(order, cfg, action, flow, flags)
    saved, lost, discount_cost, message_cost = _estimate_impact(
        order, risk, cfg, action, discount_value
    )
    decision = Decision(
        order_id=str(order.get("order_id", "")),
        action=action,
        risk=float(risk),
        discount_inr=discount_value if action == "NUDGE" else 0,
        flow=flow,
        flags=flags,
        est_saved=saved,
        est_lost=lost,
        est_discount_cost=discount_cost,
        est_msg_cost=message_cost,
        llm_source=str(order.get("llm_source", "rules")),
        config_hash=config_hash(),
    )
    facts = {**order, **text, "address_score": score, "name_fake": fake}
    return Decision(**{**decision.__dict__, "reason": build_reason(decision, facts)})
