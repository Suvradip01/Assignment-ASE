"""Auditable expected-value and discount calculations."""
from typing import Any
import numpy as np

def rto_cost(cfg: Any) -> float:
    """Calculate logistics and expected damage cost for one RTO."""
    c = cfg["costs"]
    return float(c["forward_shipping"] + c["return_shipping"] + c["packaging_handling"] + c["damaged_share_of_returns"] * c["product_cost"])

def value_at_stake(order: dict[str, Any], cfg: Any) -> float:
    """Calculate contribution and acquisition spend at risk."""
    c = cfg["costs"]
    return float(c["gross_margin_pct"] * float(order.get("order_value", 0)) + (c["customer_acquisition_cost"] if int(order.get("customer_prior_orders", 0)) == 0 else 0))

def ev_ship(p: float, order: dict[str, Any], cfg: Any) -> float:
    """Expected value of shipping COD without intervention."""
    return (1-p)*value_at_stake(order,cfg)-p*rto_cost(cfg)

def ev_confirm(p: float, order: dict[str, Any], cfg: Any) -> float:
    """Expected value of the confirmation flow."""
    a,c=cfg["assumptions"],cfg["costs"]
    return -p*(1-a["confirm_catches_share_of_returns"])*rto_cost(cfg)+(1-p)*(1-a["confirm_loses_share_of_genuine"])*value_at_stake(order,cfg)-c["whatsapp_message_cost"]

def prepaid_rto(p: float, cfg: Any) -> float:
    """Estimate prepaid return probability from COD risk ratio."""
    c=cfg["costs"]
    return max(0.01,p*c["prepaid_rto_rate"]/c["cod_rto_rate"])

def net_saving(p: float, order: dict[str, Any], cfg: Any) -> float:
    """Estimate shipping savings from converting COD to prepaid."""
    c=cfg["costs"]
    return p*(1-c["prepaid_rto_rate"]/c["cod_rto_rate"])*rto_cost(cfg)-c["payment_gateway_fee_pct"]*float(order.get("order_value",0))

def discount(p: float, order: dict[str, Any], cfg: Any) -> float:
    """Return a viable rounded prepaid discount, or zero."""
    offer=cfg["prepaid_offer"]; saving=net_saving(p,order,cfg)
    if saving <= 0: return 0.0
    step=float(offer["round_to_inr"]); amount=round(offer["share_of_saving_given_to_customer"]*saving/step)*step
    amount=max(amount,float(offer["min_discount_inr"]))
    amount=min(amount,float(offer["max_discount_pct"])/100*float(order.get("order_value",0)),(1-offer["company_keeps_at_least_share"])*saving)
    return float(round(amount,2)) if amount >= offer["min_discount_inr"] else 0.0

def conversion_rate(p: float, discount_inr: float, cfg: Any) -> float:
    """Interpolate genuine customer conversion and discount effect."""
    table=cfg["assumptions"]["prepaid_conversion_by_discount_pct"]; pct=discount_inr/max(1e-9,1.0)
    return float((1-p)*np.interp(pct, list(map(float,table)), list(table.values())))

def ev_nudge(p: float, order: dict[str, Any], cfg: Any, offer: float | None = None) -> float:
    """Expected value of prepaid nudge then confirmation fallback."""
    d=discount(p,order,cfg) if offer is None else offer; conv=conversion_rate(p,d/max(1,float(order.get("order_value",0)))*100,cfg); pp=prepaid_rto(p,cfg); stake=value_at_stake(order,cfg)
    return conv*((1-pp)*(stake-d)-pp*rto_cost(cfg))+(1-conv)*ev_confirm(p,order,cfg)-cfg["costs"]["whatsapp_message_cost"]
