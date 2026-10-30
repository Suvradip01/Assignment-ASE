"""Small deterministic WhatsApp conversation simulator."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import yaml
from engine.whatsapp.parser import Intent, parse_reply
from engine.llm import classify_reply
from engine.config import load_config

@dataclass
class Conversation:
    """Persistable simulator conversation state."""
    order_id: str; state: str; risk: float; flow: str; sent_at: datetime; last_at: datetime; language: str="en"; messages: int=0; clarifications: int=0; msg_ids: set[str]=field(default_factory=set); address_update: str=""; queued_message: str=""; template_values: dict[str, str]=field(default_factory=dict)

def _render(key: str, language: str, values: dict[str, str]) -> str:
    """Render one local English or Hinglish message template."""
    templates=yaml.safe_load(Path("config/whatsapp_templates.yaml").read_text(encoding="utf-8"))
    template=templates[key].get("hi" if language=="hi" else "en",templates[key].get("en",""))
    return template.format(**values)

def start_conversation(decision: Any, order: dict[str,Any], now: datetime) -> tuple[Conversation,list[str]]:
    """Start a confirmation or prepaid-choice conversation."""
    cfg=load_config(); quiet=cfg["whatsapp"]["quiet_hours"]; hour=now.hour*60+now.minute; start=int(quiet["start"][:2])*60+int(quiet["start"][3:]); end=int(quiet["end"][:2])*60+int(quiet["end"][3:]); is_quiet=hour>=start or hour<end
    flow=decision.flow or "confirm"; state="QUEUED" if is_quiet else "AWAITING_ADDRESS" if flow=="confirm_address" else "AWAITING_PREPAID_CHOICE" if flow.startswith("nudge") else "AWAITING_CONFIRMATION"
    language="hi" if order.get("state") in cfg["whatsapp"]["hinglish_states"] or order.get("address_language") in {"hindi","hinglish"} else "en"
    order_value=float(order.get("order_value",0) or 0); discount=float(getattr(decision,"discount_inr",0) or 0)
    values={"first_name":str(order.get("customer_name","Customer")).split()[0],"brand":cfg["brand_name"],"order_id":str(order.get("order_id",decision.order_id)),"items":str(order.get("items","your items")),"order_value":f"{order_value:,.0f}","address_short":str(order.get("address", "address not provided"))[:80],"city":str(order.get("city","")),"pincode":str(order.get("pincode","")),"discount":f"{discount:.0f}","prepaid_total":f"{max(0,order_value-discount):.0f}"}
    key="confirm_address" if flow=="confirm_address" else "nudge_prepaid_only" if flow=="nudge_prepaid_only" else "nudge_prepaid" if flow.startswith("nudge") else "confirm_cod"
    initial=_render(key,language,values)
    conv=Conversation(decision.order_id,state,decision.risk,flow,now,now,language=language,messages=0 if is_quiet else 1,queued_message=initial,template_values=values)
    return conv,[] if is_quiet else [initial]

def handle_inbound(conv: Conversation,text: str,msg_id: str,now: datetime) -> tuple[Conversation,list[str]]:
    """Apply a single idempotent inbound message."""
    if msg_id in conv.msg_ids: return conv,[]
    conv.msg_ids.add(msg_id); conv.last_at=now; intent=parse_reply(text,conv.state); messages=[]
    if conv.state in {"CONFIRMED_SHIP_COD","PAID_SHIP_PREPAID","AUTO_SHIPPED_NO_REPLY","OPTED_OUT","NEEDS_HUMAN"}:
        return conv,["This conversation is already closed."]
    if conv.state in {"CANCELLED_BY_CUSTOMER","CANCELLED_NO_REPLY"}:
        conv.state="AWAITING_CONFIRMATION"; messages=["Reopened order conversation."]; return conv,messages
    if intent.value=="STOP": conv.state="OPTED_OUT"; return conv,[_render("opt_out_ack",conv.language,conv.template_values)]
    if intent.needs_llm:
        classified = classify_reply(text, conv.state)
        prepaid = conv.state in {"AWAITING_PREPAID_CHOICE", "AWAITING_PAYMENT"}
        intent = Intent({"confirm": "KEEP_COD" if prepaid else "YES", "cancel": "CANCEL" if prepaid else "NO", "change_address": "CHANGE_ADDRESS"}.get(classified, "UNCLEAR"))
    if intent.value=="CHANGE_ADDRESS": conv.state="AWAITING_ADDRESS"; return conv,[_render("confirm_address",conv.language,conv.template_values)]
    if conv.state=="AWAITING_ADDRESS" and intent.value=="ADDRESS": conv.address_update=text; conv.state="NEEDS_HUMAN"; return conv,[_render("address_received",conv.language,conv.template_values)]
    if conv.state in {"AWAITING_CONFIRMATION","AWAITING_ADDRESS"}:
        if intent.value=="YES": conv.state="CONFIRMED_SHIP_COD"; messages=[_render("confirmed_ack",conv.language,conv.template_values)]
        elif intent.value=="NO": conv.state="CANCELLED_BY_CUSTOMER"; messages=[_render("cancelled_ack",conv.language,conv.template_values)]
    else:
        if intent.value=="PAID" and conv.state=="AWAITING_PAYMENT": conv.state="PAID_SHIP_PREPAID"; messages=[_render("prepaid_ack",conv.language,conv.template_values)]
        elif intent.value in {"YES","PAY"}: conv.state="AWAITING_PAYMENT"; messages=[_render("payment_link",conv.language,conv.template_values)]
        elif intent.value=="KEEP_COD": conv.state="CONFIRMED_SHIP_COD"; messages=[_render("confirmed_ack",conv.language,conv.template_values)]
        elif intent.value in {"NO","CANCEL"}: conv.state="CANCELLED_BY_CUSTOMER"; messages=[_render("cancelled_ack",conv.language,conv.template_values)]
    if intent.value=="UNCLEAR":
        conv.clarifications+=1; limit=int(load_config()["whatsapp"]["max_clarification_messages"]); conv.state="NEEDS_HUMAN" if conv.clarifications>=limit else conv.state; messages=[_render("human_handoff",conv.language,conv.template_values) if conv.state=="NEEDS_HUMAN" else _render("clarify",conv.language,conv.template_values)]
    return conv,messages

def tick(conv: Conversation,now: datetime) -> tuple[Conversation,list[str]]:
    """Send a reminder or apply the 24-hour no-reply rule."""
    cfg=load_config(); conv.last_at=now
    if conv.state=="QUEUED" and now.hour>=int(cfg["whatsapp"]["quiet_hours"]["end"][:2]):
        conv.state="AWAITING_PREPAID_CHOICE" if conv.flow.startswith("nudge") else "AWAITING_ADDRESS" if conv.flow=="confirm_address" else "AWAITING_CONFIRMATION"
        conv.sent_at=now; conv.last_at=now; conv.messages=1
        return conv,[conv.queued_message]
    elapsed=(now-conv.sent_at).total_seconds()/3600
    if conv.state not in {"AWAITING_CONFIRMATION","AWAITING_PREPAID_CHOICE","AWAITING_ADDRESS","QUEUED"}: return conv,[]
    if elapsed>=cfg["whatsapp"]["timeout_after_hours"]:
        conv.state="NEEDS_HUMAN" if conv.flow=="confirm_address" else "CANCELLED_NO_REPLY" if conv.risk>=cfg["rules"]["no_reply_cancel_if_risk_at_least"] else "AUTO_SHIPPED_NO_REPLY"
        key="human_handoff" if conv.state=="NEEDS_HUMAN" else "no_reply_cancelled" if conv.state=="CANCELLED_NO_REPLY" else "confirmed_ack"
        return conv,[_render(key,conv.language,conv.template_values)]
    if elapsed>=cfg["whatsapp"]["reminder_after_hours"] and conv.messages==1: conv.messages+=1; return conv,[_render("reminder",conv.language,conv.template_values)]
    return conv,[]
