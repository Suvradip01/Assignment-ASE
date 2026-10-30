# Overview: COD Order Decision Engine (Take-Home)

Build everything described in these spec files. Read `00_overview.md` and `01_config.md` first, then work phase by phase.

## File index (build in this order)

| File | Content |
|---|---|
| `00_overview.md` | Goal, LLM vs maths line, repo layout, coding rules, order schema |
| `01_config.md` | `config/settings.yaml` and validation |
| `02_phase1_data.md` | Phase 1: cleaning, geo, findings |
| `03_phase2_text_checks.md` | Phase 2: text rules + LLM layer |
| `04_phase3_model.md` | Phase 3: features + risk model |
| `05_phase4_decision_engine.md` | Phase 4: economics, decision rules, reasons |
| `06_phase5_whatsapp.md` | Phase 5: WhatsApp flow mock |
| `07_phase6_dashboard.md` | Phase 6: dashboard + app pages |
| `08_phase7_backtest_memo.md` | Phase 7: backtest, discount maths, memo numbers |
| `09_docs_tests_done.md` | Docs scaffolds, edge cases, tests, definition of done, don'ts |

## Goal in one paragraph

A D2C haircare brand ships ~3,000 orders/month, 55% COD. ~28% of COD orders become RTO (returned). One RTO costs about ₹169. Cancelling a genuine first order costs about ₹700 (margin + ad cost). Build a system that scores every new COD order and picks one of 4 actions: **SHIP**, **CONFIRM** (WhatsApp), **NUDGE** (prepaid discount), **HOLD**. Every decision has a plain-English reason. Thresholds live in a YAML file a non-technical person can edit. Include a WhatsApp flow mock, a one-screen dashboard, and the numbers needed for a business memo.

**Stack:** Python 3.11, pandas, numpy, scikit-learn, joblib, pyyaml, streamlit, sqlite3 (stdlib), python-dotenv, pytest, plus the Groq SDK for optional text enrichment. No other frameworks.

**Where the LLM is used (and where it is not)**

| Job | Tool | Why |
|---|---|---|
| Is this address complete/deliverable? Hinglish addresses | LLM | Messy text, rules fail |
| Is this name fake ("asdf", "Test Order")? | LLM (+ rules) | Same |
| Understand odd customer WhatsApp replies (only when the keyword parser fails) | LLM | Free-text Hinglish intent |
| Probability an order is returned | scikit-learn model | Numbers, small data, needs calibration |
| Action choice, thresholds, ₹ maths, discount size | Plain code + YAML | Must be repeatable, auditable, free |
| Reason text | Template code | Consistent, no hallucination |
| Yes/No/Haan/Nahi replies | Keyword parser | Cheap, deterministic |

The LLM never decides the action and never outputs a probability. It only produces text-derived features. If the LLM is down, the system keeps working using rule-based fallbacks.


## Repo layout (create exactly this)

```
cod-decision-engine/
├── README.md
├── AGENTS.md
├── spec/            # these spec files
├── requirements.txt
├── .env.example            # LLM_PROVIDER=none|groq, provider key, LLM_MODEL
├── .gitignore              # .env, .venv, __pycache__, data/app.db, models/
├── config/
│   ├── settings.yaml       # ALL business-editable numbers (see 01_config.md)
│   └── whatsapp_templates.yaml
├── prompts/
│   ├── address_name_check.txt
│   └── reply_intent.txt
├── data/
│   ├── orders_sample.csv   # provided by user
│   └── llm_cache.jsonl     # committed; lets the repo run without an API key
├── engine/
│   ├── config.py           # load + validate settings.yaml
│   ├── cleaning.py
│   ├── geo.py              # pincode prefix -> state map
│   ├── text_rules.py       # heuristic address/name/phone checks
│   ├── llm.py              # client, batching, cache, fallback
│   ├── features.py
│   ├── model.py            # train / evaluate / save / load / predict
│   ├── economics.py        # all ₹ maths (costs, EV, discount)
│   ├── decision.py         # overrides + bands -> action
│   ├── reasons.py
│   ├── store.py            # sqlite helpers
│   ├── metrics.py          # dashboard aggregates + backtest
│   └── whatsapp/
│       ├── parser.py
│       ├── templates.py
│       └── flow.py
├── scripts/
│   ├── run_all.py          # clean -> features -> train -> backtest -> score all -> docs numbers
│   ├── build_llm_cache.py  # one-time, needs API key
│   ├── explore.py          # prints/saves the findings table
│   ├── train.py
│   ├── suggest_thresholds.py
│   ├── discount_table.py
│   ├── backtest.py
│   ├── eval_llm.py
│   └── memo_numbers.py
├── app/
│   ├── Home.py             # founder dashboard
│   └── pages/
│       ├── 1_Try_an_order.py
│       ├── 2_WhatsApp_simulator.py
│       └── 3_What_if.py    # stretch
├── tests/
├── models/                 # generated
└── docs/
    ├── DECISION_LOG.md
    ├── AI_USAGE_LOG.md
    ├── data_quality.md     # generated
    └── memo_numbers.md     # generated
```


## Coding rules

- Simple functions over classes. Classes only for dataclasses (`Order`, `Decision`, `Conversation`).
- Type hints on every function. Docstring: one line.
- No function longer than ~40 lines. No clever one-liners.
- **No `datetime.now()` inside logic.** Pass `now` as a parameter (makes tests and the time-travel simulator work). Only entry points call `now()`.
- Timezone: `Asia/Kolkata` everywhere. Dataset timestamps are naive, treat them as IST.
- All numbers come from `settings.yaml`. No magic numbers in code. Fixed seed 42 everywhere.
- One shared `clean_orders()` used for training AND serving (prevents train/serve mismatch).
- Never print or commit secrets. Read keys from env only.
- Log with `logging`, not `print`, except in scripts' final summaries.


## Input schema for a new order (serving)

Required: `order_id, order_datetime, customer_name, phone, address, city, state, pincode, order_value, num_items, items, customer_prior_orders, customer_prior_rto, utm_source`. Optional: `courier`. Missing optional or malformed fields must never crash scoring: the order gets flags and (if it cannot be assessed) a safe default of CONFIRM with reason "Could not assess: missing <field>". Order value ≤ 0 → HOLD.
