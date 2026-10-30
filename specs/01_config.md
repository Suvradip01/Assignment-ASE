# Config: `config/settings.yaml`

## `config/settings.yaml` (write it with these plain-English comments)

```yaml
brand_name: "Kesh"            # shown in WhatsApp messages (placeholder)

# ----- COSTS in ₹ (from the brief) -----
costs:
  forward_shipping: 65
  return_shipping: 65
  packaging_handling: 25
  damaged_share_of_returns: 0.08   # 8% of returned products are unsellable
  product_cost: 180
  gross_margin_pct: 0.62
  customer_acquisition_cost: 300   # wasted if we lose a first-time customer
  whatsapp_message_cost: 1.0       # assumption, ~₹1 per message
  payment_gateway_fee_pct: 0.02    # assumption, charged on prepaid orders
  cod_rto_rate: 0.28
  prepaid_rto_rate: 0.04

# ----- WHEN TO DO WHAT -----
# "risk" = estimated chance (0 to 1) the COD order is returned.
#   risk below ship_below            -> SHIP
#   ship_below up to nudge_from      -> CONFIRM on WhatsApp
#   nudge_from up to hold_at         -> NUDGE to prepaid
#   hold_at or above                 -> HOLD (ops reviews / cancels)
# First-time customers get a higher HOLD bar: we paid ₹300 to get them.
risk_bands:
  first_time_customer: { ship_below: 0.25, nudge_from: 0.35, hold_at_or_above: 0.85 }
  repeat_customer:     { ship_below: 0.20, nudge_from: 0.35, hold_at_or_above: 0.80 }

# ----- EXTRA RULES (checked BEFORE the risk bands) -----
rules:
  min_order_value: 1                      # 0 or negative -> HOLD (bad data)
  junk_address_below_score: 0.30          # address scoring below this is "not deliverable"
  repeat_returner_min_prior_rto: 2        # this many past returns -> COD not offered (prepaid only)
  blocked_pincodes: []                    # HOLD any COD order to these
  prepaid_only_pincodes: []               # COD not offered here
  blocked_phones: []
  no_reply_cancel_if_risk_at_least: 0.50  # after 24h of silence: cancel if risk >= this, else ship anyway
  max_hold_share_alert: 0.10              # dashboard warns if >10% of a day's orders are HOLD
  control_group_pct: 0.0                  # stretch: % of risky orders shipped anyway to measure truth

# ----- PREPAID DISCOUNT -----
prepaid_offer:
  share_of_saving_given_to_customer: 0.5  # we give back half of the money we expect to save
  min_discount_inr: 20
  max_discount_pct: 10                    # never more than 10% of order value
  company_keeps_at_least_share: 0.2       # discount <= 80% of net saving, so we never lose money on a conversion
  round_to_inr: 5

# ----- WHATSAPP -----
whatsapp:
  quiet_hours: { start: "21:00", end: "09:00" }   # no messages at night; queue to 09:00
  reminder_after_hours: 4
  timeout_after_hours: 24
  payment_link_valid_hours: 12
  reopen_window_days: 7
  max_clarification_messages: 2
  max_messages_per_order: 4
  hinglish_states: [Uttar Pradesh, Bihar, Madhya Pradesh, Rajasthan, Delhi]

# ----- ASSUMPTIONS NOT IN THE DATA (replace with real numbers after launch) -----
assumptions:
  confirm_catches_share_of_returns: 0.40   # of orders that would RTO, share stopped by confirmation
  confirm_loses_share_of_genuine: 0.03     # genuine customers lost by asking
  nudge_annoyed_cancel_share: 0.01
  prepaid_conversion_by_discount_pct:      # share of GENUINE customers who switch to prepaid (multiplied by 1-risk)
    0: 0.05
    3: 0.10
    5: 0.15
    8: 0.22
    10: 0.25

# ----- MODEL -----
model:
  use_courier: false         # courier may not be known before shipping (leakage); keep off
  use_time_features: false   # hour/weekday looked like noise; test in ablation
  test_month: "2026-09"      # time-based holdout
```

`config.py` must validate on load and raise a **plain-English error** (e.g. `hold_at_or_above (0.30) must be higher than nudge_from (0.35) in first_time_customer`). Checks: all probabilities in [0,1]; `ship_below < nudge_from < hold_at_or_above` for both groups; costs ≥ 0; conversion table sorted and in [0,1]; quiet hours parse as HH:MM; `share_of_saving_given_to_customer` in [0,1]. Return a frozen dataclass. Streamlit pages re-read the file on every run, so edits take effect on refresh.
