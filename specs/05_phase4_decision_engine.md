# Phase 4: Economics, decision engine, reasons

> Read `00_overview.md` and `01_config.md` first. Finish this phase (tests + acceptance command) before starting the next.


### `engine/economics.py` (all ₹ maths lives here)

```
rto_cost            = forward + return + packaging + damaged_share * product_cost      # = 169.4
margin(order)       = gross_margin_pct * order_value
value_at_stake(o)   = margin(o) + (CAC if first_time else 0)     # what we lose if we cancel a genuine order

ev_ship(p, o)       = (1-p) * value_at_stake - p * rto_cost
ev_confirm(p, o)    = -p*(1-catch)*rto_cost + (1-p)*(1-drop)*value_at_stake - msg_cost
prepaid_rto(p)      = max(0.01, p * prepaid_rto_rate / cod_rto_rate)          # prepaid customers return ~1/7 as often
net_saving(p, o)    = p*(1 - prepaid_rto_rate/cod_rto_rate)*rto_cost - gateway_fee_pct*order_value
discount(p, o)      = see below
conv(p, d)          = interp(discount_pct, table) * (1 - p)                  # only genuine customers switch
ev_nudge(p, o, d)   = conv*[(1-pp)*(value_at_stake - d) - pp*rto_cost] + (1-conv)*ev_confirm - msg_cost   (pp = prepaid_rto(p))
```

**Discount rule (show this maths in the memo):**
1. `saving = net_saving(p, order)`.
2. `d = share_of_saving_given_to_customer * saving`, rounded to nearest `round_to_inr`.
3. Clamp: `max(d, min_discount_inr)` then `min(d, max_discount_pct% * order_value, (1 - company_keeps_at_least_share) * saving)`.
4. If `saving` is too small so the clamp makes `d < min_discount_inr` → return 0 and skip the nudge (downgrade to CONFIRM).
Worked example to put in the test: AOV ₹649, risk 0.50 → saving ≈ 0.5×0.857×169.4 − 0.02×649 ≈ ₹59.6 → d ≈ ₹30. Company still nets ≈ ₹30 per conversion before counting that the customer is now far less likely to return.

Per-order **estimated ₹ impact vs. "ship everything"** (used by the dashboard; stored at decision time):

| Action | est_saved | est_lost | extra costs |
|---|---|---|---|
| SHIP | 0 | 0 | 0 |
| CONFIRM | p·catch·rto_cost | (1-p)·drop·value_at_stake | msg_cost |
| NUDGE | conv·(p − pp)·rto_cost | (1-p)·nudge_annoyed·(1-conv)·value_at_stake | conv·d (discount) + msg_cost |
| HOLD | p·rto_cost | (1-p)·value_at_stake | 0 |

`net = est_saved − est_lost − discount_cost − msg_cost`. The dashboard must label these **estimates, not measured results** (no counterfactual exists).

### `scripts/suggest_thresholds.py`
Sweeps risk 0.00–1.00 (step 0.01) for first-time and repeat customers at average order value, and prints the EV-optimal cut-offs: `ship_below` = first p where `ev_confirm > ev_ship`; `hold_at` = first p where `ev_confirm < 0`; `nudge_from` = first p where `ev_nudge − ev_confirm >= 10`. Prints a ready-to-paste YAML block and a table of EV per action at p = 0.1…0.9. It does NOT edit the config. With the default assumptions it should land near: first-time ≈ 0.25 / 0.21–0.35 / 0.87, repeat ≈ 0.17 / 0.38 / 0.80. The committed `settings.yaml` values are the rounded, human-chosen ones. Verify and note any difference in the decision log.

### `engine/decision.py` → `decide(order_row, risk, cfg, text_flags) -> Decision`

`Decision` fields: `order_id, action, risk, reason, discount_inr, flow ("confirm"|"confirm_address"|"nudge"|"nudge_prepaid_only"|None), flags (list[str]), est_saved, est_lost, est_discount_cost, est_msg_cost, llm_source, model_version, config_hash, control_group, decided_at`.

**Precedence (first match wins):**
1. `order_value < min_order_value` → HOLD, flag `invalid_order_value`.
2. Phone in `blocked_phones` or pincode in `blocked_pincodes` → HOLD, flag `manual_block`.
3. Address junk (score < `junk_address_below_score`) AND (fake name OR invalid phone) → HOLD, flag `undeliverable_details`.
4. Compute band action from risk and customer type (first-time vs repeat).
5. Address junk only → action is at least CONFIRM using flow `confirm_address` (asks for a full address). Even if the band says SHIP. If the band says NUDGE, still use `confirm_address` first (a prepaid discount does not fix an undeliverable address).
6. `customer_prior_rto >= repeat_returner_min_prior_rto` or pincode in `prepaid_only_pincodes` → action is at least NUDGE with flow `nudge_prepaid_only` (no "keep COD" button). HOLD from the band still wins.
7. NUDGE chosen but `discount()` returns 0 → downgrade to CONFIRM, flag `discount_not_viable`.
8. Control group (stretch): if `control_group_pct > 0` and `hash(order_id) % 100 < pct*100` and the action is CONFIRM/NUDGE/HOLD → action SHIP, flag `control_group`, keep `would_have_been` in flags.

Every Decision is deterministic for the same inputs. Re-scoring the same `order_id` UPSERTs, never duplicates.

### `engine/reasons.py` → `build_reason(decision, facts) -> str`
Template only (no LLM). Format:

`<ACTION>: <risk>% chance of return (COD average 28%). Why: <up to 3 reasons>. <one ₹ line>.`

Pick up to 3 triggered facts in this priority: override rule that fired; `prior_rto >= 2` ("2 past returns"); fake name; junk address; pincode history ("pincode 846043: 61% of 33 past COD orders returned", only if n ≥ 10, else city/state); pin/state mismatch; first-time customer; invalid phone; high order value. ₹ line examples: `Shipping as-is risks about ₹70 on average; a WhatsApp check costs ₹1.` / `Prepaid offer of ₹30 off: we expect to save about ₹60.` / `Holding avoids an expected ₹150 loss but may lose a real customer worth about ₹700.` Max ~45 words. Never empty. Never show model internals.

**Acceptance:** `pytest` covers: band boundaries (value equal to a threshold goes to the higher-risk bucket), precedence order, first-time vs repeat difference, discount worked example, discount not viable → CONFIRM, junk-address override, repeat-returner override, empty reason impossible, config hash changes when YAML changes. `python -m scripts.suggest_thresholds` runs.
