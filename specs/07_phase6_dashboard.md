# Phase 6: Dashboard and pages

> Read `00_overview.md` and `01_config.md` first. Finish this phase (tests + acceptance command) before starting the next.


### `engine/store.py` (SQLite `data/app.db`)
Tables: `decisions` (PK order_id; columns of `Decision` plus `order_date`, `is_first_time`, `order_value`, `state`, `city`), `conversations`, `messages` (UNIQUE inbound msg_id). Create if missing.

### `scripts/run_all.py`
Single command: clean → text checks (cache/rules) → features → train → backtest → score every historical order into `decisions` → write `docs/memo_numbers.md`. Prints a short summary. Must finish in a few minutes on a laptop with no API key.

### `app/Home.py` (the founder's morning screen, one page, no tabs)
- Date picker, default = **yesterday in IST**. If that day has no orders (the sample data ends 2026-09-30), show the latest day with data and a small note "No orders yesterday, showing <date>".
- Row 1: four big tiles = counts for SHIP / CONFIRM / NUDGE / HOLD, with % of the day.
- Row 2: **₹ saved from avoided RTOs**, **₹ lost from cancelled/lost genuine orders**, **discounts + message costs**, **Net ₹ impact** (green/red). Under every ₹ number: "Estimate, based on model risk, not measured". Tooltip explains each formula in one sentence.
- Row 3: 14-day net ₹ trend (st.line_chart) and bucket mix per day (st.bar_chart).
- Row 4: "Needs a human" table: HOLD orders and `NEEDS_HUMAN` conversations with order id, value, reason. Top 10.
- Alerts (yellow box): HOLD share above `max_hold_share_alert`; LLM fallback share > 20% of the day's orders; > 30% UNCLEAR WhatsApp replies; day with 0 orders.
- Sidebar: link to `config/settings.yaml` explanation and the active config hash.
- Handles empty DB with a friendly "Run `python -m scripts.run_all` first".

### `app/pages/1_Try_an_order.py`
Form for one new order (all fields from the order schema in `00_overview.md`, with 4 preset buttons: "clean repeat customer", "first-time Bihar junk address", "fake name", "repeat returner"). Calls the same `clean → text check → features → predict → decide → reason` path as batch scoring. Shows action, risk %, reason, discount, flags, expected ₹ per action side by side.

### `app/pages/3_What_if.py` (stretch)
Sliders for the band thresholds; recomputes the backtest ₹ on the held-out month live. Never writes the YAML. Shows: ₹ net, number of HOLD of first-time customers, number of genuine orders lost.

**Acceptance:** `streamlit run app/Home.py` loads with data after `run_all`; changing a threshold in `settings.yaml` and re-running `run_all` changes bucket counts; empty-DB state does not crash.
