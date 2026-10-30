"""Deterministic action selection and impact estimates."""
from dataclasses import dataclass, field
from typing import Any
import hashlib
import pandas as pd
from engine.economics import discount, rto_cost, value_at_stake, conversion_rate, prepaid_rto
from engine.config import config_hash
from engine.reasons import build_reason

@dataclass(frozen=True)
class Decision:
    """A scored order decision and its expected impact."""
    order_id: str; action: str; risk: float; reason: str = ""; discount_inr: float = 0.0; flow: str | None = None; flags: list[str] = field(default_factory=list)
    est_saved: float = 0.0; est_lost: float = 0.0; est_discount_cost: float = 0.0; est_msg_cost: float = 0.0; llm_source: str = "rules"; model_version: str = "logistic-v1"; config_hash: str = ""; control_group: bool = False; decided_at: str = ""

def decide(order_row: dict[str, Any], risk: float, cfg: Any, text_flags: dict[str, Any] | None = None) -> Decision:
    """Apply rule precedence, risk bands, and deterministic impact maths."""
    order=dict(order_row); flags=[]; tf=text_flags or {}; rules=cfg["rules"]; action="SHIP"; flow=None; d=0.0
    if order.get("order_value") is not None and not pd.isna(order.get("order_value")) and float(order["order_value"])<rules["min_order_value"]:
        invalid=Decision(str(order.get("order_id","")),"HOLD",float(risk),reason="HOLD: invalid order value. Why: order value is below the configured minimum. Holding prevents scoring bad data.",flags=["invalid_order_value"],config_hash=config_hash())
        return invalid
    missing=order.get("missing_fields","")
    if missing:
        first_missing=str(missing).split(", ")[0]
        safe=Decision(str(order.get("order_id","")),"CONFIRM",float(risk),reason=f"Could not assess: missing {first_missing}",flow="confirm",flags=["missing_required_field"],config_hash=config_hash())
        return safe
    required=["order_id","order_datetime","customer_name","phone","address","city","state","pincode","order_value","num_items","items","customer_prior_orders","customer_prior_rto","utm_source"]
    missing=[key for key in required if key not in order or order[key] is None or pd.isna(order[key]) or (isinstance(order[key],str) and not order[key].strip())]
    if missing:
        safe=Decision(str(order.get("order_id","")),"CONFIRM",float(risk),reason=f"Could not assess: missing {missing[0]}",flow="confirm",flags=["missing_required_field"],config_hash=config_hash())
        return safe
    first=int(order.get("customer_prior_orders",0) or 0)==0; band=cfg["risk_bands"]["first_time_customer" if first else "repeat_customer"]
    score=float(tf.get("address_score",order.get("address_score",1))); fake=bool(tf.get("name_fake",order.get("name_fake",False))); phone=str(order.get("phone", "")); pin=str(order.get("pincode", ""))
    if float(order.get("order_value",0) or 0)<rules["min_order_value"]: action="HOLD"; flags.append("invalid_order_value")
    elif phone in rules["blocked_phones"] or pin in rules["blocked_pincodes"]: action="HOLD"; flags.append("manual_block")
    elif score<rules["junk_address_below_score"] and (fake or int(order.get("phone_valid",1) or 0)==0): action="HOLD"; flags.append("undeliverable_details")
    elif risk>=band["hold_at_or_above"]: action="HOLD"
    elif risk>=band["nudge_from"]: action="NUDGE"; flow="nudge"
    elif risk>=band["ship_below"]: action="CONFIRM"; flow="confirm"
    if action!="HOLD" and score<rules["junk_address_below_score"]:
        if action in {"SHIP","NUDGE"}: action="CONFIRM"
        flow="confirm_address"; flags.append("junk_address")
    if action!="HOLD" and (int(order.get("customer_prior_rto",0) or 0)>=rules["repeat_returner_min_prior_rto"] or pin in rules["prepaid_only_pincodes"]):
        if action in {"SHIP","CONFIRM"}: action="NUDGE"
        if action=="NUDGE": flow="nudge_prepaid_only"
        flags.append("prepaid_only")
    if action=="NUDGE":
        d=discount(risk,order,cfg)
        if d==0: action="CONFIRM"; flow="confirm"; flags.append("discount_not_viable")
    pct=float(rules["control_group_pct"])
    if pct>0 and action in {"CONFIRM","NUDGE","HOLD"}:
        bucket=int(hashlib.sha256(str(order.get("order_id","")).encode()).hexdigest()[:8],16)%100
        if bucket<pct*100:
            flags.append(f"would_have_been_{action}"); action="SHIP"; flow=None
    conv=conversion_rate(risk,d/max(1,float(order.get("order_value",0)))*100,cfg) if action=="NUDGE" else 0
    pp=prepaid_rto(risk,cfg); stake=value_at_stake(order,cfg)
    saved=(risk*cfg["assumptions"]["confirm_catches_share_of_returns"]*rto_cost(cfg) if action=="CONFIRM" else risk*rto_cost(cfg) if action=="HOLD" else conv*(risk-pp)*rto_cost(cfg) if action=="NUDGE" else 0)
    lost=(1-risk)*(cfg["assumptions"]["confirm_loses_share_of_genuine"]*stake if action=="CONFIRM" else stake if action=="HOLD" else cfg["assumptions"]["nudge_annoyed_cancel_share"]*(1-conv)*stake if action=="NUDGE" else 0)
    decision=Decision(str(order.get("order_id","")),action,float(risk),discount_inr=d if action=="NUDGE" else 0,flow=flow,flags=flags,est_saved=saved,est_lost=lost,est_discount_cost=conv*d if action=="NUDGE" else 0,est_msg_cost=cfg["costs"]["whatsapp_message_cost"] if action in {"CONFIRM","NUDGE"} else 0,llm_source=str(order.get("llm_source","rules")),config_hash=config_hash())
    return Decision(**{**decision.__dict__,"reason":build_reason(decision,{**order,**tf,"address_score":score,"name_fake":fake})})
