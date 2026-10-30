# Phase 7: Backtest and memo numbers

> Read `00_overview.md` and `01_config.md` first. Finish this phase (tests + acceptance command) before starting the next.


### `scripts/backtest.py`
Uses `models/oof_predictions.csv` (no leakage). For the **held-out month (Sep 2026)** and for **all months**:

Compare four policies against "ship everything" (today):
1. **Ship all** (baseline, also Marketing's position).
2. **Ops proposal:** HOLD if risk ≥ 0.50, plus HOLD any city or state whose training-fold RTO ≥ 40%; else SHIP.
3. **Our rules** (current `settings.yaml`).
4. **Our rules, but first-time bands set equal to repeat bands** (shows the cost/benefit of the Marketing protection).

For each: counts per action; RTOs avoided (actual labels for SHIP/HOLD, expected formulas for CONFIRM/NUDGE); genuine orders lost; ₹ saved; ₹ lost (incl. CAC for first-time); discounts; message cost; **net ₹**; number of first-time customers cancelled. Realised outcomes for SHIP/HOLD use the actual label; CONFIRM/NUDGE use the assumption-based expected formulas. State this in the output.

Also output:
- Scale to the real business: the sample has about 330 orders/month vs ~1,650 COD orders/month, so multiply by `1650 / sample_orders_per_month` and label it "scaled".
- **Sensitivity table:** net ₹ when `confirm_catches_share_of_returns` ∈ {0.2, 0.4, 0.6} and `confirm_loses_share_of_genuine` ∈ {0.01, 0.03, 0.08}; and prepaid conversion ×0.5 / ×1 / ×1.5. Show the break-even: the catch rate at which net turns negative.

### `scripts/discount_table.py`
Prints and saves the Part 2 maths: for AOV ₹649 (and ₹349, ₹1,198) and risk 0.30/0.40/0.50/0.70: expected saving, discount offered, customer benefit %, company net per conversion, expected conversion. Plus a "discount vs expected net ₹" sweep (₹0–₹80 step ₹5) for risk 0.5 showing why ~₹30 is near the best and why bigger discounts lose money.

### `scripts/memo_numbers.py` → `docs/memo_numbers.md`
Everything the memo needs, each number traceable: 5+ findings, model metrics, policy comparison, "what the rules would have done to September" (counts per bucket, first-time customers touched), the ₹ trade-off Ops vs Marketing, sensitivity, discount maths. **The human writes the memo in their own words from these numbers. Codex must not write the memo.**

**Acceptance:** `python -m scripts.backtest`, `discount_table`, `memo_numbers` run and produce readable tables; numbers in `memo_numbers.md` match a manual recomputation in a test on a 20-row fixture.
