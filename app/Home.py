"""Founder-facing daily COD decision dashboard."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from engine.config import load_config
from engine.metrics import dashboard_aggregates
from engine.store import connect

st.set_page_config(page_title="COD Order Decision Engine", layout="wide")
st.title("COD order decision engine")
st.caption("Estimated impact based on model risk, not measured results")
cfg = load_config()
st.sidebar.markdown("Edit business thresholds in `config/settings.yaml`.")
db = connect()
data = pd.read_sql_query("SELECT * FROM decisions", db)
conversations = pd.read_sql_query("SELECT * FROM conversations", db)
messages = pd.read_sql_query("SELECT * FROM messages", db)
db.close()
if data.empty:
    st.info("Run `python -m scripts.run_all` first.")
    st.stop()

data["order_date"] = pd.to_datetime(data.order_date, errors="coerce").dt.date
latest = data.order_date.max()
yesterday = datetime.now(ZoneInfo("Asia/Kolkata")).date() - timedelta(days=1)
selected = st.date_input("Order date", value=yesterday)
day = data[data.order_date == selected]
if day.empty:
    selected = latest
    day = data[data.order_date == latest]
    st.caption(f"No orders yesterday, showing {selected}.")

metrics = dashboard_aggregates(day)
bucket_columns = st.columns(4)
for column, action in zip(bucket_columns, ["SHIP", "CONFIRM", "NUDGE", "HOLD"]):
    column.metric(
        action,
        f"{metrics['counts'][action]} ({metrics['counts'][action] / max(1, metrics['n']):.0%})",
    )

money_columns = st.columns(4)
for column, label, key in zip(
    money_columns,
    ["₹ saved", "₹ lost", "Discounts + messages", "Net ₹ impact"],
    ["saved", "lost", "costs", "net"],
):
    column.metric(
        label,
        f"₹{metrics[key]:,.0f}",
        help="Estimate based on model risk, not measured.",
    )
    column.caption("Estimate, not measured")

trend = (
    data.groupby("order_date")[
        ["est_saved", "est_lost", "est_discount_cost", "est_msg_cost"]
    ]
    .sum()
    .tail(14)
)
trend["net"] = (
    trend.est_saved - trend.est_lost - trend.est_discount_cost - trend.est_msg_cost
)
st.subheader("14-day estimated net ₹ trend")
st.line_chart(trend["net"])
st.subheader("Action mix by day")
mix = data.groupby(["order_date", "action"]).size().unstack(fill_value=0).tail(14)
st.bar_chart(mix)

human_rows = data[data.action == "HOLD"][["order_id", "order_value", "reason"]].copy()
if not conversations.empty:
    needs_review = conversations[conversations.state == "NEEDS_HUMAN"]["order_id"]
    extra = data[data.order_id.isin(needs_review)][
        ["order_id", "order_value", "reason"]
    ]
    human_rows = pd.concat([human_rows, extra]).drop_duplicates("order_id")
st.subheader("Needs a human")
st.dataframe(human_rows.head(10), width="stretch")

if metrics["n"] == 0:
    st.warning("No orders for this date.")
else:
    hold_share = metrics["counts"]["HOLD"] / metrics["n"]
    if hold_share > cfg["rules"]["max_hold_share_alert"]:
        st.warning("HOLD share is above the configured alert level.")
    fallback_share = (
        float(day.llm_source.isin(["rules"]).mean()) if "llm_source" in day else 1.0
    )
    llm_used = (
        bool(day.llm_source.isin(["groq", "cache"]).any())
        if "llm_source" in day
        else False
    )
    if fallback_share > cfg["rules"]["llm_fallback_share_alert"] and llm_used:
        st.warning(
            f"Text-check fallback share is {fallback_share:.0%}; review provider availability."
        )
if not messages.empty:
    inbound = messages[messages.direction == "inbound"]
    if len(inbound):
        from engine.whatsapp.parser import parse_reply

        unclear_share = float(
            inbound.body.map(
                lambda body: parse_reply(str(body), "AWAITING_CONFIRMATION").value
                == "UNCLEAR"
            ).mean()
        )
        if unclear_share > cfg["rules"]["unclear_reply_share_alert"]:
            st.warning(
                f"Unclear WhatsApp reply share is {unclear_share:.0%}; review the reply flow."
            )
