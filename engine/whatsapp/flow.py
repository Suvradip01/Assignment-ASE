"""Small deterministic WhatsApp conversation simulator."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from engine.config import load_config
from engine.llm import classify_reply
from engine.whatsapp.parser import Intent, parse_reply

CLOSED_STATES = {
    "CONFIRMED_SHIP_COD",
    "PAID_SHIP_PREPAID",
    "AUTO_SHIPPED_NO_REPLY",
    "OPTED_OUT",
    "NEEDS_HUMAN",
}
OPEN_STATES = {
    "AWAITING_CONFIRMATION",
    "AWAITING_PREPAID_CHOICE",
    "AWAITING_ADDRESS",
    "QUEUED",
}


@dataclass
class Conversation:
    """Persistable simulator conversation state."""

    order_id: str
    state: str
    risk: float
    flow: str
    sent_at: datetime
    last_at: datetime
    language: str = "en"
    messages: int = 0
    clarifications: int = 0
    msg_ids: set[str] = field(default_factory=set)
    address_update: str = ""
    queued_message: str = ""
    template_values: dict[str, str] = field(default_factory=dict)


def _render(key: str, language: str, values: dict[str, str]) -> str:
    """Render one local English or Hinglish message template."""
    templates = yaml.safe_load(
        Path("config/whatsapp_templates.yaml").read_text(encoding="utf-8")
    )
    template = templates[key].get(
        "hi" if language == "hi" else "en", templates[key].get("en", "")
    )
    return template.format(**values)


def _is_quiet_time(now: datetime, settings: dict[str, Any]) -> bool:
    """Check whether the current local time is within configured quiet hours."""
    quiet = settings["whatsapp"]["quiet_hours"]
    current_minute = now.hour * 60 + now.minute
    start = int(quiet["start"][:2]) * 60 + int(quiet["start"][3:])
    end = int(quiet["end"][:2]) * 60 + int(quiet["end"][3:])
    return current_minute >= start or current_minute < end


def _initial_state(flow: str, queued: bool) -> str:
    """Choose the starting state for the selected conversation flow."""
    if queued:
        return "QUEUED"
    if flow == "confirm_address":
        return "AWAITING_ADDRESS"
    if flow.startswith("nudge"):
        return "AWAITING_PREPAID_CHOICE"
    return "AWAITING_CONFIRMATION"


def _message_language(order: dict[str, Any], settings: dict[str, Any]) -> str:
    """Choose Hinglish for configured regions or Hinglish source text."""
    is_hinglish = order.get("state") in settings["whatsapp"][
        "hinglish_states"
    ] or order.get("address_language") in {"hindi", "hinglish"}
    return "hi" if is_hinglish else "en"


def _template_values(
    decision: Any, order: dict[str, Any], settings: dict[str, Any]
) -> dict[str, str]:
    """Prepare safe display values for the selected message template."""
    order_value = float(order.get("order_value", 0) or 0)
    discount_value = float(getattr(decision, "discount_inr", 0) or 0)
    customer_name = str(order.get("customer_name", "Customer")).split()
    first_name = customer_name[0] if customer_name else "Customer"
    return {
        "first_name": first_name,
        "brand": settings["brand_name"],
        "order_id": str(order.get("order_id", decision.order_id)),
        "items": str(order.get("items", "your items")),
        "order_value": f"{order_value:,.0f}",
        "address_short": str(order.get("address", "address not provided"))[:80],
        "city": str(order.get("city", "")),
        "pincode": str(order.get("pincode", "")),
        "discount": f"{discount_value:.0f}",
        "prepaid_total": f"{max(0, order_value - discount_value):.0f}",
    }


def _template_key(flow: str) -> str:
    """Select the template for a confirmation or prepaid conversation."""
    if flow == "confirm_address":
        return "confirm_address"
    if flow == "nudge_prepaid_only":
        return "nudge_prepaid_only"
    if flow.startswith("nudge"):
        return "nudge_prepaid"
    return "confirm_cod"


def start_conversation(
    decision: Any, order: dict[str, Any], now: datetime
) -> tuple[Conversation, list[str]]:
    """Start a confirmation or prepaid-choice conversation."""
    settings = load_config()
    flow = decision.flow or "confirm"
    queued = _is_quiet_time(now, settings.data)
    language = _message_language(order, settings.data)
    values = _template_values(decision, order, settings.data)
    initial_message = _render(_template_key(flow), language, values)
    conversation = Conversation(
        decision.order_id,
        _initial_state(flow, queued),
        decision.risk,
        flow,
        now,
        now,
        language=language,
        messages=0 if queued else 1,
        queued_message=initial_message,
        template_values=values,
    )
    return conversation, [] if queued else [initial_message]


def _handle_system_intent(
    conversation: Conversation, text: str, intent: Intent
) -> tuple[bool, list[str]]:
    """Handle closed, reopened, opt-out, and address messages."""
    if conversation.state in CLOSED_STATES:
        return True, ["This conversation is already closed."]
    if conversation.state in {"CANCELLED_BY_CUSTOMER", "CANCELLED_NO_REPLY"}:
        conversation.state = "AWAITING_CONFIRMATION"
        return True, ["Reopened order conversation."]
    if intent.value == "STOP":
        conversation.state = "OPTED_OUT"
        return True, [
            _render("opt_out_ack", conversation.language, conversation.template_values)
        ]
    if intent.value == "CHANGE_ADDRESS":
        conversation.state = "AWAITING_ADDRESS"
        return True, [
            _render(
                "confirm_address", conversation.language, conversation.template_values
            )
        ]
    if conversation.state == "AWAITING_ADDRESS" and intent.value == "ADDRESS":
        conversation.address_update = text
        conversation.state = "NEEDS_HUMAN"
        return True, [
            _render(
                "address_received", conversation.language, conversation.template_values
            )
        ]
    return False, []


def _classify_unclear(text: str, conversation: Conversation, intent: Intent) -> Intent:
    """Use Groq only when the deterministic reply parser asks for help."""
    if not intent.needs_llm:
        return intent
    classified = classify_reply(text, conversation.state)
    prepaid = conversation.state in {"AWAITING_PREPAID_CHOICE", "AWAITING_PAYMENT"}
    mapping = {
        "confirm": "KEEP_COD" if prepaid else "YES",
        "cancel": "CANCEL" if prepaid else "NO",
        "change_address": "CHANGE_ADDRESS",
    }
    return Intent(mapping.get(classified, "UNCLEAR"))


def _handle_confirmation_intent(
    conversation: Conversation, intent: Intent
) -> list[str]:
    """Apply YES or NO while awaiting COD confirmation or an address."""
    if intent.value == "YES":
        conversation.state = "CONFIRMED_SHIP_COD"
        return [
            _render(
                "confirmed_ack", conversation.language, conversation.template_values
            )
        ]
    if intent.value == "NO":
        conversation.state = "CANCELLED_BY_CUSTOMER"
        return [
            _render(
                "cancelled_ack", conversation.language, conversation.template_values
            )
        ]
    return []


def _handle_prepaid_intent(conversation: Conversation, intent: Intent) -> list[str]:
    """Apply payment, COD, or cancellation replies in the prepaid flow."""
    if intent.value == "PAID" and conversation.state == "AWAITING_PAYMENT":
        conversation.state = "PAID_SHIP_PREPAID"
        return [
            _render("prepaid_ack", conversation.language, conversation.template_values)
        ]
    if intent.value in {"YES", "PAY"}:
        conversation.state = "AWAITING_PAYMENT"
        return [
            _render("payment_link", conversation.language, conversation.template_values)
        ]
    if intent.value == "KEEP_COD":
        conversation.state = "CONFIRMED_SHIP_COD"
        return [
            _render(
                "confirmed_ack", conversation.language, conversation.template_values
            )
        ]
    if intent.value in {"NO", "CANCEL"}:
        conversation.state = "CANCELLED_BY_CUSTOMER"
        return [
            _render(
                "cancelled_ack", conversation.language, conversation.template_values
            )
        ]
    return []


def _clarify_unclear_reply(conversation: Conversation, intent: Intent) -> list[str]:
    """Clarify an unsupported reply or hand the conversation to a human."""
    if intent.value != "UNCLEAR":
        return []
    conversation.clarifications += 1
    maximum = int(load_config()["whatsapp"]["max_clarification_messages"])
    if conversation.clarifications >= maximum:
        conversation.state = "NEEDS_HUMAN"
        template = "human_handoff"
    else:
        template = "clarify"
    return [_render(template, conversation.language, conversation.template_values)]


def handle_inbound(
    conversation: Conversation, text: str, msg_id: str, now: datetime
) -> tuple[Conversation, list[str]]:
    """Apply a single idempotent inbound message."""
    if msg_id in conversation.msg_ids:
        return conversation, []
    conversation.msg_ids.add(msg_id)
    conversation.last_at = now
    intent = parse_reply(text, conversation.state)
    handled, messages = _handle_system_intent(conversation, text, intent)
    if handled:
        return conversation, messages
    intent = _classify_unclear(text, conversation, intent)
    if conversation.state in {"AWAITING_CONFIRMATION", "AWAITING_ADDRESS"}:
        messages = _handle_confirmation_intent(conversation, intent)
    else:
        messages = _handle_prepaid_intent(conversation, intent)
    if intent.value == "UNCLEAR":
        messages = _clarify_unclear_reply(conversation, intent)
    return conversation, messages


def _start_queued_message(
    conversation: Conversation, now: datetime, settings: dict[str, Any]
) -> list[str] | None:
    """Send a message queued during quiet hours when the window opens."""
    quiet_end = int(settings["whatsapp"]["quiet_hours"]["end"][:2])
    if conversation.state != "QUEUED" or now.hour < quiet_end:
        return None
    conversation.state = _initial_state(conversation.flow, queued=False)
    conversation.sent_at = now
    conversation.last_at = now
    conversation.messages = 1
    return [conversation.queued_message]


def _timeout_message(conversation: Conversation, settings: dict[str, Any]) -> list[str]:
    """Apply the configured no-reply outcome and return its message."""
    if conversation.flow == "confirm_address":
        conversation.state = "NEEDS_HUMAN"
        template = "human_handoff"
    elif conversation.risk >= settings["rules"]["no_reply_cancel_if_risk_at_least"]:
        conversation.state = "CANCELLED_NO_REPLY"
        template = "no_reply_cancelled"
    else:
        conversation.state = "AUTO_SHIPPED_NO_REPLY"
        template = "confirmed_ack"
    return [_render(template, conversation.language, conversation.template_values)]


def tick(conversation: Conversation, now: datetime) -> tuple[Conversation, list[str]]:
    """Send a reminder or apply the 24-hour no-reply rule."""
    settings = load_config().data
    conversation.last_at = now
    queued_messages = _start_queued_message(conversation, now, settings)
    if queued_messages is not None:
        return conversation, queued_messages
    elapsed_hours = (now - conversation.sent_at).total_seconds() / 3600
    if conversation.state not in OPEN_STATES:
        return conversation, []
    if elapsed_hours >= settings["whatsapp"]["timeout_after_hours"]:
        return conversation, _timeout_message(conversation, settings)
    should_remind = (
        elapsed_hours >= settings["whatsapp"]["reminder_after_hours"]
        and conversation.messages == 1
    )
    if should_remind:
        conversation.messages += 1
        return conversation, [
            _render("reminder", conversation.language, conversation.template_values)
        ]
    return conversation, []
