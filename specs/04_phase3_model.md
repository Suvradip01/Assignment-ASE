# Phase 3: Features and model

> Read `00_overview.md` and `01_config.md` first. Finish this phase (tests + acceptance command) before starting the next.


### `engine/features.py` → `build_features(df) -> df`

| Feature | Notes |
|---|---|
| `state` | one-hot; unseen → ignore |
| `city_g` | city, but cities with < 15 training orders → `"Other"` |
| `pin3` | first 3 pincode digits, groups with < 10 orders → `"Other"`; missing → `"Unknown"` |
| `pincode_missing`, `pin_state_mismatch` | flags |
| `is_first_time` | `customer_prior_orders == 0` |
| `customer_prior_orders`, `customer_prior_rto`, `prior_rto_rate` | rate = rto/orders, 0 if no orders |
| `value_bin` | order_value quantile bins (5), one-hot (the curve is non-monotonic) |
| `num_items` | |
| `utm_source` | one-hot |
| `address_score` | LLM if available else rules |
| `address_junk_rule` | always from rules |
| `name_fake` | LLM OR rules |
| `phone_valid` | |
| `address_has_digit` | |

Excluded by default: `courier` (probably not known at decision time; check in ablation and record the result), time-of-day/weekday (config flags). Never use `order_id`, `customer_name` text, raw `phone`, or `final_status`.

### `engine/model.py`
- Two candidates: (a) `LogisticRegression` (L2, C chosen by CV from `[0.1, 0.3, 1, 3]`) with one-hot + scaling; (b) `HistGradientBoostingClassifier` (small: depth ≤ 3, ~150 iterations, early stopping).
- **No `class_weight`.** We need calibrated probabilities for ₹ maths.
- Calibrate probabilities (`CalibratedClassifierCV(method="sigmoid", cv=5)`).
- Evaluate: stratified 5-fold CV and a **time split** (train before `test_month`, test on it). Report ROC-AUC, PR-AUC, log loss, Brier, a 10-bin calibration table, and lift ("top 20% riskiest orders contain X% of all RTOs").
- Pick **logistic unless GB beats it by > 0.02 AUC AND is not worse on log loss**. Prefer simple.
- Ablation table: drop each feature group (geography, customer history, text, value, source, courier, time) and show the change in AUC and log loss. Save to `models/ablation.csv`.
- Final model retrained on all clean labeled rows. Save `models/model.joblib`, `models/metrics.json`, `models/calibration.csv`, `models/pincode_stats.csv`.
- `predict_risk(df) -> np.ndarray` clipped to `[0.01, 0.99]`.
- **Out-of-fold predictions for every historical order** saved to `models/oof_predictions.csv` (used by the backtest so no order is scored by a model that saw its own label).
- `pincode_stats.csv`: per pincode `n`, `returned`, smoothed rate `(returned + m*parent) / (n + m)` with m=20, parent = pin3 rate (itself smoothed toward state, then global). Used only for reasons and ops views, never as a raw 100% on tiny samples.

**Acceptance:** `python -m scripts.train` prints metrics and writes all files; CV AUC is reported honestly (expect roughly 0.65–0.80; do not tune against the test month); calibration table has no bin off by more than ~0.10 with n ≥ 30; unknown state/city/pincode at predict time works.
