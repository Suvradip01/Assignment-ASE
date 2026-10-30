# Docs, edge cases, tests, definition of done

> Apply throughout; finish with this file.

## Documents (Codex creates the scaffolds, the human fills them)

- `README.md`: what it is (3 lines); **run in under 10 minutes** (copy-paste block below); architecture picture (ASCII); where to edit thresholds (point to `config/settings.yaml`, explain each block in plain words); the LLM vs maths line and why; how to add an API key (optional); how to run tests; known limits; folder map.
  ```
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  python -m scripts.run_all
  streamlit run app/Home.py
  pytest
  ```
- `docs/DECISION_LOG.md`: pre-fill with these entries (what, alternatives, why), human edits later: hybrid ML + LLM instead of LLM-only; logistic over GBM (data size, explainability, calibration); courier excluded (leakage risk); time features excluded (noise); no class weights (calibration); YAML bands + EV script instead of hidden thresholds; higher HOLD bar for first-time customers (CAC); discount = share of net saving with a hard ceiling; no-reply policy by risk; keyword parser first, LLM only for leftovers; send only name+address to the LLM (privacy); cache committed; sample size ~330 orders/month vs ~1,650 real, scaled in the memo; delivered-order margin assumed to already include shipping (brief is ambiguous); damage cost applied once per RTO (not per item); PDF title says "AI Automation Engineer" while the role is "Associate Software Engineer".
- `docs/AI_USAGE_LOG.md`: table skeleton only (tool, task, outcome) and three empty "AI got this wrong / how I caught it / fix" blocks. **Do not invent entries.** The human records real ones.


## Edge-case checklist (every item needs a test or an explicit code path)

**Data:** duplicate rows; duplicate order_id with different content; status typos; IN_TRANSIT; order_value 0; invalid/9-digit/`+91` phones; missing/6-digit-invalid pincode; missing city; prior_rto > prior_orders; pincode/state mismatch; address `.`, `xyz`, `home`, `call me`; fake names; unseen state/city/pincode; extra whitespace, mixed case; unicode/Hindi script address; 500-char address.

**Model:** training leakage via pincode statistics (use pin3 one-hot or out-of-fold rates only); probabilities clipped to [0.01, 0.99]; model file missing → clear error telling the user to run `scripts.train`; model trained with LLM features but served with fallback rules (log `llm_source`, show the fallback share on the dashboard).

**LLM:** no key; network error; timeout; 429; invalid JSON; missing ids; scores out of range; prompt-injection text in an address; cost guard (batch + cache); no PII beyond name/address/city/state/pincode sent.

**Decision:** threshold equality; first-time vs repeat bands; override precedence; NUDGE with non-viable discount; junk address with low risk; repeat returner with low risk; control group; same order scored twice; config edited with a bad value → friendly error and the app refuses to start instead of silently using defaults.

**WhatsApp:** quiet hours; reminder timing; duplicate inbound; late reply; STOP; unclear ×N; address reply; payment link expired; message cap; customer replies in Hinglish; emoji-only; empty message; opted-out phone gets nothing.

**Dashboard:** no orders yesterday; empty DB; HOLD share alert; all orders in one bucket; division by zero in percentages; timezone boundary (order at 23:55 IST counts for that IST date).


## Tests (`pytest`, fast, no network, no API key)

`test_cleaning.py`, `test_text_rules.py`, `test_llm.py` (fake client: garbage JSON, missing ids, cache hit makes 0 calls, no-key fallback), `test_config.py` (every validation message), `test_economics.py` (rto_cost = 169.4; discount worked example; EV formulas), `test_decision.py`, `test_reasons.py`, `test_parser.py` (table of ≥ 40 phrases including Hinglish, emoji, "no problem"), `test_flow.py` (injected clock), `test_metrics.py` (dashboard aggregates on a 20-row fixture), `test_model_smoke.py` (train on 200 synthetic rows, predict on unseen categories).


## Definition of done

- [ ] `pip install -r requirements.txt && python -m scripts.run_all && streamlit run app/Home.py` works on a clean machine with **no API key** in under 10 minutes.
- [ ] `pytest` passes.
- [ ] All 4 actions produced; every decision has a reason of ≤ ~45 words.
- [ ] Editing `config/settings.yaml` changes behaviour; bad values give a plain-English error.
- [ ] WhatsApp simulator demonstrates yes / no / random / silence-24h / STOP / address reply.
- [ ] Dashboard shows yesterday's 4 buckets, ₹ saved, ₹ lost, discounts+messages, net, all labelled as estimates.
- [ ] `docs/memo_numbers.md`, `data_quality.md`, `findings.md` generated from code, not typed by hand.
- [ ] README, DECISION_LOG, AI_USAGE_LOG scaffolds exist.
- [ ] No secrets in git; `.env.example` present.


## Do NOT

- Do not use the LLM for risk probability, thresholds, ₹ maths, discount, or action choice.
- Do not hardcode thresholds, costs or rates in code.
- Do not use `final_status` (or anything created after delivery) as a feature.
- Do not use `class_weight` or SMOTE.
- Do not claim "₹ saved" is measured. It is an estimate.
- Do not write the business memo or fabricate AI-usage-log entries.
- Do not add Docker, Postgres, Redis, Celery, React or extra frameworks.
- Do not silently swallow errors. Fall back **and** record the fallback.
