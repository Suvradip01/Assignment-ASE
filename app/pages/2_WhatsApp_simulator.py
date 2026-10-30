"""Interactive local mock for confirmation and prepaid conversations."""
from datetime import datetime, timedelta
import streamlit as st
from engine.whatsapp.flow import start_conversation, handle_inbound, tick
from engine.decision import Decision
from engine.store import save_conversation, record_message

st.title("WhatsApp simulator")
st.warning("MOCK, nothing is sent")

def add_messages(role: str, messages: list[str]) -> None:
    """Append messages to the visible simulator transcript."""
    st.session_state.chat.extend({"role": role, "text": item} for item in messages)

if "conv" not in st.session_state:
    kind = st.radio("Example flow", ["CONFIRM", "NUDGE"], horizontal=True)
    if st.button("Start example conversation"):
        flow = "nudge" if kind == "NUDGE" else "confirm"
        decision = Decision("DEMO", kind, 0.4, flow=flow)
        now = datetime.now().astimezone()
        conv, outbound = start_conversation(decision, {"order_id": "DEMO", "customer_name": "Asha", "items": "Shampoo", "order_value": 649, "address": "12 MG Road, near market", "city": "Delhi", "state": "Delhi", "pincode": "110001"}, now)
        st.session_state.conv = conv
        st.session_state.chat = []
        add_messages("assistant", outbound)
        save_conversation(conv)
        for body in outbound:
            record_message(conv.order_id, "outbound", None, body, now.isoformat())
        st.rerun()

if "conv" in st.session_state:
    conv = st.session_state.conv
    st.write("State:", conv.state)
    for item in st.session_state.chat:
        with st.chat_message(item["role"]):
            st.write(item["text"])

    if conv.state in {"AWAITING_CONFIRMATION", "AWAITING_ADDRESS"}:
        quick_replies = [("Yes, confirm", "YES"), ("No, cancel", "NO")]
    elif conv.state in {"AWAITING_PREPAID_CHOICE", "AWAITING_PAYMENT"}:
        quick_replies = [("Pay online", "PAY"), ("Keep COD", "KEEP_COD"), ("Cancel", "CANCEL")]
    else:
        quick_replies = []
    cols = st.columns(max(1, len(quick_replies)))
    for col, (label, value) in zip(cols, quick_replies):
        if col.button(label, key=f"quick_{value}"):
            now = datetime.now().astimezone(); msg_id = f"quick-{now.timestamp()}"
            conv, outbound = handle_inbound(conv, value, msg_id, now)
            st.session_state.conv = conv
            add_messages("user", [label])
            add_messages("assistant", outbound)
            save_conversation(conv)
            record_message(conv.order_id, "inbound", msg_id, label, now.isoformat())
            for body in outbound:
                record_message(conv.order_id, "outbound", None, body, now.isoformat())
            st.rerun()

    with st.form("reply_form"):
        message = st.text_input("Customer reply")
        submitted = st.form_submit_button("Send reply")
    if submitted:
        now = datetime.now().astimezone(); msg_id = f"typed-{now.timestamp()}"
        conv, outbound = handle_inbound(conv, message, msg_id, now)
        st.session_state.conv = conv
        add_messages("user", [message or "(empty message)"])
        add_messages("assistant", outbound)
        save_conversation(conv)
        record_message(conv.order_id, "inbound", msg_id, message or "", now.isoformat())
        for body in outbound:
            record_message(conv.order_id, "outbound", None, body, now.isoformat())
        st.rerun()

    hours = st.selectbox("Advance time", [4, 24, 48])
    if st.button("Advance"):
        now = conv.last_at + timedelta(hours=hours)
        conv, outbound = tick(conv, now)
        st.session_state.conv = conv
        add_messages("assistant", outbound)
        save_conversation(conv)
        for body in outbound:
            record_message(conv.order_id, "outbound", None, body, now.isoformat())
        st.rerun()

    if st.button("Reset simulator"):
        del st.session_state.conv
        del st.session_state.chat
        st.rerun()
