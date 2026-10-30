"""Explore a held-out policy threshold without changing the YAML config."""
from copy import deepcopy
from pathlib import Path
import pandas as pd
import streamlit as st
from engine.cleaning import clean_orders, training_rows
from engine.config import Settings, load_config
from engine.decision import decide

st.title("What if?")
st.caption("Exploration uses out-of-fold predictions for September 2026 and does not edit config/settings.yaml.")
config = load_config()
oof_path = Path("models/oof_predictions.csv")
if not oof_path.exists():
    st.info("Run `python -m scripts.run_all` first to generate held-out predictions.")
    st.stop()

orders = training_rows(clean_orders(pd.read_csv("orders_sample.csv")))
predictions = pd.read_csv(oof_path)[["order_id", "risk"]]
held_out = orders.merge(predictions, on="order_id", how="inner")
held_out = held_out[held_out["order_datetime"].dt.strftime("%Y-%m") == "2026-09"]
if held_out.empty:
    st.warning("No held-out orders are available for the configured test month.")
    st.stop()

repeat_hold = float(config["risk_bands"]["repeat_customer"]["hold_at_or_above"])
hold_threshold = st.slider("Shared hold threshold", 0.5, 0.99, repeat_hold, 0.01)
data = deepcopy(config.data)
data["risk_bands"]["repeat_customer"]["hold_at_or_above"] = hold_threshold
data["risk_bands"]["first_time_customer"]["hold_at_or_above"] = hold_threshold
explore_config = Settings(data)
decisions = [decide(row.to_dict(), float(row.risk), explore_config) for row in held_out.itertuples(index=False)]
net = sum(item.est_saved - item.est_lost - item.est_discount_cost - item.est_msg_cost for item in decisions)
first_holds = sum(item.action == "HOLD" and int(row.customer_prior_orders) == 0 for item, row in zip(decisions, held_out.itertuples()))
genuine_lost = sum(item.action == "HOLD" and row.final_status == "DELIVERED" for item, row in zip(decisions, held_out.itertuples()))
st.metric("Estimated net impact", f"₹{net:,.0f}")
st.metric("First-time orders held", first_holds)
st.metric("Genuine orders held", genuine_lost)
st.caption("Estimates use model risk and configured assumptions; they are not measured results.")
