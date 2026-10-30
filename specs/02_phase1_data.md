# Phase 1: Data cleaning and findings

> Read `00_overview.md` and `01_config.md` first. Finish this phase (tests + acceptance command) before starting the next.


### `engine/cleaning.py` → `clean_orders(df) -> df`

Rules (log counts of each fix to `docs/data_quality.md`):

1. Strip whitespace on all string columns.
2. `final_status`: uppercase + strip. Valid: `DELIVERED`, `RTO`. Known dirty values in the file: `Rto`, `RTO `, `delivered`. `IN_TRANSIT` has no outcome → exclude from training, keep in a count.
3. Exact duplicate rows → drop (30 in the file). Same `order_id` with different content → keep the row with the latest `order_datetime`.
4. `order_value <= 0` (3 rows) → excluded from training. At serving time this triggers HOLD ("invalid order value").
5. Phone: keep digits only; if more than 10 digits strip leading `91` or `0`; keep last 10. `phone_valid = 1` if 10 digits and starts with 6–9. Invalid phones (about 32 in the file: 9-digit, `+91 xxxxx xxxxx`) are not dropped. Fix formats that are recoverable, flag the rest.
6. Pincode: float → 6-digit string. Missing (12 rows) → `pincode_missing=1`, pin3 = `"Unknown"`. Not 6 digits or starts with 0 → missing.
7. City: trim, title-case; missing (4 rows) → `"Unknown"`.
8. `customer_prior_rto > customer_prior_orders` (4 rows) → clip prior_rto to prior_orders, log a warning.
9. Parse `order_datetime`, sort ascending.
10. `address` null → `""`.

### `engine/geo.py`
Map 2-digit pincode prefixes to states for the 11 states in the data: Delhi 11; Maharashtra 40–44; Tamil Nadu 60–64; West Bengal 70–74; Karnataka 56–59; Telangana 50; Rajasthan 30–34; Assam 78; Madhya Pradesh 45–48; Uttar Pradesh 20–28; Bihar 80–85. `pin_state_mismatch = 1` if pincode present, state known in map, and prefix not in that state's set. Unknown state → 0.

### `scripts/explore.py`
Print and save `docs/findings.md` with a table of RTO rate and count for: overall; junk-address orders; fake-name orders; by state; by city (n ≥ 20); first-time vs repeat; `customer_prior_rto` (0/1/2); utm_source × first-time; order value bins; pincode/state mismatch; invalid phone. Highlight at least 5 surprising findings with numbers. Known from a quick pass (verify, do not hardcode): junk address ≈ 65% RTO vs 26% for the rest; fake name ≈ 71%; Bihar 54%, UP 44% vs Maharashtra 18%; repeat customer with 0 past RTO ≈ 14% vs first-time ≈ 30%; prior_rto = 2 → 76%; pincode/state mismatch ≈ 48%; value bins non-monotonic.

**Acceptance:** `python -m scripts.explore` runs, writes `docs/data_quality.md` and `docs/findings.md`; unit tests for each cleaning rule pass.
