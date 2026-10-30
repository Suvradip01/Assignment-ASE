"""Score one manually entered order through the shared serving path."""
import pandas as pd
import streamlit as st
from engine.cleaning import clean_orders
from engine.config import load_config
from engine.decision import decide
from engine.economics import ev_confirm, ev_nudge, ev_ship, value_at_stake
from engine.features import build_features
from engine.model import load_model

st.title("Try an order")
presets = {
    "Clean repeat customer": {"customer_name": "Asha Sharma", "phone": "9876543210", "address": "12 MG Road, near market", "city": "Delhi", "state": "Delhi", "pincode": "110001", "order_value": 649, "customer_prior_orders": 2, "customer_prior_rto": 0},
    "First-time Bihar junk address": {"customer_name": "Asha Kumar", "phone": "9876543210", "address": "xyz", "city": "Patna", "state": "Bihar", "pincode": "800001", "order_value": 649, "customer_prior_orders": 0, "customer_prior_rto": 0},
    "Fake name": {"customer_name": "asdf", "phone": "9876543210", "address": "12 MG Road, near market", "city": "Delhi", "state": "Delhi", "pincode": "110001", "order_value": 649, "customer_prior_orders": 1, "customer_prior_rto": 0},
    "Repeat returner": {"customer_name": "Asha Sharma", "phone": "9876543210", "address": "12 MG Road, near market", "city": "Delhi", "state": "Delhi", "pincode": "110001", "order_value": 649, "customer_prior_orders": 2, "customer_prior_rto": 2},
}
preset_name = st.selectbox("Preset example", list(presets))
if st.button("Load preset"):
    for key, value in presets[preset_name].items():
        st.session_state[f"order_{key}"] = value
    st.rerun()

defaults = {
    "order_order_id": "DEMO001", "order_order_datetime": "2026-10-30 10:00",
    **{f"order_{key}": value for key, value in presets["Clean repeat customer"].items()},
    "order_items": "Shampoo", "order_num_items": 1,
    "order_utm_source": "meta_ads",
}
for key, value in defaults.items():
    st.session_state.setdefault(key, value)

with st.form("order"):
    order = {
        "order_id": st.text_input("Order ID", key="order_order_id"),
        "order_datetime": st.text_input("Order date/time", key="order_order_datetime"),
        "customer_name": st.text_input("Customer name", key="order_customer_name"),
        "phone": st.text_input("Phone", key="order_phone"),
        "address": st.text_input("Address", key="order_address"),
        "city": st.text_input("City", key="order_city"),
        "state": st.text_input("State", key="order_state"),
        "pincode": st.text_input("Pincode", key="order_pincode"),
        "order_value": st.number_input("Order value", min_value=0, key="order_order_value"),
        "items": st.text_input("Items", key="order_items"),
        "num_items": st.number_input("Items count", min_value=1, key="order_num_items"),
        "customer_prior_orders": st.number_input("Prior orders", min_value=0, key="order_customer_prior_orders"),
        "customer_prior_rto": st.number_input("Prior returns", min_value=0, key="order_customer_prior_rto"),
        "utm_source": st.text_input("Source", key="order_utm_source"),
    }
    submitted = st.form_submit_button("Score")

if submitted:
    cleaned = clean_orders(pd.DataFrame([order]))
    bundle = load_model()
    features = build_features(cleaned, use_llm=True, value_edges=bundle.get("value_edges"))
    row = features.iloc[0]
    risk = float(bundle["model"].predict_proba(features[bundle["columns"]])[:, 1][0])
    cfg = load_config()
    decision = decide(row.to_dict(), risk, cfg)
    st.write("Text check source:", row["llm_source"])
    st.metric(decision.action, f"{risk:.1%} return risk")
    st.write(decision.reason)
    st.write("Discount", decision.discount_inr)
    st.write("Flags", decision.flags)
    stake = value_at_stake(row.to_dict(), cfg)
    expected_values = {"SHIP": ev_ship(risk, row.to_dict(), cfg), "CONFIRM": ev_confirm(risk, row.to_dict(), cfg), "NUDGE": ev_nudge(risk, row.to_dict(), cfg), "HOLD": 0.0}
    st.subheader("Expected ₹ value by action")
    columns = st.columns(4)
    for column, action in zip(columns, ["SHIP", "CONFIRM", "NUDGE", "HOLD"]):
        column.metric(action, f"₹{expected_values[action]:,.0f}")
    st.caption(f"Order contribution at stake: ₹{stake:,.0f}. Values are model estimates, not measured results.")
