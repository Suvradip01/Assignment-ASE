"""Regression tests for the interactive WhatsApp mock."""
from datetime import datetime, timedelta
from pathlib import Path
from engine.decision import Decision
from engine.whatsapp.flow import handle_inbound, start_conversation, tick
from engine.whatsapp.parser import parse_reply
from engine.store import save_conversation, record_message, connect


def test_prepaid_quick_replies() -> None:
    """Map prepaid buttons and payment confirmation to distinct intents."""
    assert parse_reply("KEEP_COD", "AWAITING_PREPAID_CHOICE").value == "KEEP_COD"
    assert parse_reply("PAY", "AWAITING_PREPAID_CHOICE").value == "PAY"
    assert parse_reply("PAID", "AWAITING_PAYMENT").value == "PAID"


def test_confirm_flow_yes_and_duplicate_message() -> None:
    """Confirm an order once when an inbound message is duplicated."""
    now = datetime(2026, 10, 30, 10)
    conv, _ = start_conversation(Decision("T1", "CONFIRM", .3, flow="confirm"), {"order_id": "T1"}, now)
    conv, messages = handle_inbound(conv, "haan", "msg-1", now + timedelta(minutes=1))
    assert conv.state == "CONFIRMED_SHIP_COD" and messages
    conv, messages = handle_inbound(conv, "haan", "msg-1", now + timedelta(minutes=2))
    assert conv.state == "CONFIRMED_SHIP_COD" and messages == []


def test_nudge_keep_cod_and_payment() -> None:
    """Handle prepaid, keep-COD and paid states safely."""
    now = datetime(2026, 10, 30, 10)
    conv, _ = start_conversation(Decision("T2", "NUDGE", .4, flow="nudge"), {"order_id": "T2"}, now)
    conv, _ = handle_inbound(conv, "KEEP_COD", "keep", now)
    assert conv.state == "CONFIRMED_SHIP_COD"
    conv, _ = start_conversation(Decision("T3", "NUDGE", .4, flow="nudge"), {"order_id": "T3"}, now)
    conv, _ = handle_inbound(conv, "PAY", "pay", now)
    assert conv.state == "AWAITING_PAYMENT"
    conv, _ = handle_inbound(conv, "PAID", "paid", now + timedelta(minutes=1))
    assert conv.state == "PAID_SHIP_PREPAID"


def test_timeout_policy_and_address_handoff() -> None:
    """Apply the configured no-reply branch and route junk addresses to a human."""
    now = datetime(2026, 10, 30, 10)
    low, _ = start_conversation(Decision("T4", "CONFIRM", .3, flow="confirm"), {"order_id": "T4"}, now)
    low, _ = tick(low, now + timedelta(hours=24))
    assert low.state == "AUTO_SHIPPED_NO_REPLY"
    address, _ = start_conversation(Decision("T5", "CONFIRM", .7, flow="confirm_address"), {"order_id": "T5"}, now)
    address, _ = tick(address, now + timedelta(hours=24))
    assert address.state == "NEEDS_HUMAN"


def test_quiet_hours_queue_starts_clock_at_release() -> None:
    """Queue overnight messages and begin the response clock on morning release."""
    start = datetime(2026, 10, 30, 22)
    conv, outbound = start_conversation(Decision("T6", "CONFIRM", .3, flow="confirm"), {"order_id": "T6"}, start)
    assert conv.state == "QUEUED" and outbound == []
    release = start + timedelta(hours=11)
    conv, outbound = tick(conv, release)
    assert conv.state == "AWAITING_CONFIRMATION" and conv.sent_at == release and outbound


def test_mock_conversation_persists_and_inbound_is_idempotent(tmp_path: Path) -> None:
    """Persist state and deduplicate repeated inbound message IDs."""
    now = datetime(2026, 10, 30, 10)
    conv, _ = start_conversation(Decision("T7", "CONFIRM", .3, flow="confirm"), {"order_id": "T7", "customer_name": "Asha", "order_value": 649}, now)
    conv, _ = handle_inbound(conv, "yes", "same-id", now + timedelta(minutes=1))
    db_path = str(tmp_path / "state.sqlite")
    save_conversation(conv, db_path)
    record_message("T7", "inbound", "same-id", "yes", now.isoformat(), db_path)
    record_message("T7", "inbound", "same-id", "yes", now.isoformat(), db_path)
    db = connect(db_path)
    stored_state = db.execute("SELECT state FROM conversations WHERE order_id='T7'").fetchone()[0]
    stored_count = db.execute("SELECT COUNT(*) FROM messages WHERE msg_id='same-id'").fetchone()[0]
    db.close()
    assert stored_state == "CONFIRMED_SHIP_COD" and stored_count == 1
