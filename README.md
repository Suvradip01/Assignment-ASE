# COD Order Decision Engine

A decision support app for reducing Cash on Delivery (COD) returns to origin (RTO) for a direct-to-consumer haircare brand.
It estimates return risk from historical order data and recommends SHIP, CONFIRM, NUDGE to prepaid, or HOLD.
It includes a WhatsApp flow simulator, a founder dashboard, and repeatable data and backtest reports.

## Run locally

Use Python 3.11. From the repository root, run these commands in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m scripts.run_all
python -m streamlit run app/Home.py
```

Open <http://localhost:8501>. The first pipeline run cleans the included `orders_sample.csv`, trains and evaluates the model, scores orders into a local SQLite database, and regenerates the reports under `docs/`. It needs no API key. Stop the app with `Ctrl+C`.

To run the automated checks, open another terminal in the repository, activate the environment, and run:

```powershell
python -m pytest
```

### Optional Groq text checks

The app works without a provider key using local text rules and the committed text-feature cache. To enable Groq for live text checks in **Try an order**:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set:

```dotenv
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
LLM_MODEL=openai/gpt-oss-20b
```

Restart Streamlit after changing `.env`. The Try an order page shows whether its text check came from `groq`, `cache`, or `rules`. The batch pipeline intentionally uses local text rules; it does not send every historical order to Groq. The dashboard explains this so a rule-based batch is not mistaken for a provider outage.

The text checker may send only customer name, address, city, and state. It never sends phone numbers, order IDs, or order values. If Groq is not configured or a request fails, the app uses local rules instead of failing the order.

## How it works

```text
orders_sample.csv
       |
       v
clean and validate -> text checks -> tabular risk model -> estimated risk
                                                        |
                                  YAML thresholds + deterministic economics
                                                        |
                            SHIP / CONFIRM / NUDGE / HOLD + reason
                                                        |
                                     SQLite -> Streamlit dashboard

WhatsApp simulator -> templates + reply parser -> mock conversation state
```

The model estimates the chance of RTO. Python rules and YAML settings choose the action, discount, and expected-value calculations. The optional LLM is limited to language-dependent text checks and unclear WhatsApp reply classification; it never sets risk, thresholds, costs, discounts, or actions. Deterministic rules handle common replies such as yes/no and Hinglish equivalents.

## App pages

- **Home:** daily action counts, estimated financial impact, recent trends, and orders needing human review.
- **Try an order:** score a manually entered example or preset; inspect risk, action, explanation, flags, text-check source, and estimated action values.
- **WhatsApp simulator:** exercise confirmation and prepaid flows, customer replies, and timeouts. It is a mock; no messages or payments are sent.
- **What if?:** change a hold threshold for exploration and see estimated held-out policy impact. It does not edit the saved configuration.

All dashboard ₹ amounts are estimates based on model risk and configured assumptions, not measured savings or losses.

## Change business settings

Edit [`config/settings.yaml`](config/settings.yaml):

- `costs`: shipping, packaging, damage, margin, acquisition, and payment assumptions.
- `risk_bands`: action thresholds for first-time and repeat customers.
- `rules`: minimum order value, manual overrides, and alert levels.
- `prepaid_offer`: discount calculation limits and customer/company split.
- `whatsapp`: quiet hours, reminders, timeouts, and message limits.
- `assumptions`: estimated confirmation and prepaid response behavior.
- `analysis`: backtest comparison and sensitivity scenarios.

Invalid settings raise a validation error. The What if? page is for exploration only; change YAML to change the configured business policy.

## Reports and project records

The pipeline creates or updates these generated reports:

- [`docs/data_quality.md`](docs/data_quality.md): cleaning and data quality summary.
- [`docs/findings.md`](docs/findings.md): segment findings generated from the sample.
- [`docs/backtest_summary.md`](docs/backtest_summary.md): policy comparison and sensitivity analysis.
- [`docs/discount_table.md`](docs/discount_table.md): discount economics.
- [`docs/memo_numbers.md`](docs/memo_numbers.md): generated figures for use in the founder memo.
- [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md): implementation choices and rationale.

The generated numbers are estimates from a small historical sample and configured assumptions. They should not be presented as measured business results.

## Assignment submission checklist

- [x] Runnable application, source code, sample data, and run instructions.
- [x] Decision log and generated analysis/backtest figures.
- [ ] Founder business memo (1–2 pages): write this using the generated figures and findings; it is intentionally not included here.
- [ ] AI usage log: complete [`docs/AI_USAGE_LOG.md`](docs/AI_USAGE_LOG.md) with the tools actually used and examples you personally reviewed; the template is intentionally blank.
- [ ] GitHub submission: publish this repository or grant the hiring team access. No remote is configured in this local checkout.

## Known limits

- The supplied dataset is a small historical sample and may not represent current customer behavior or the full monthly order volume.
- Risk scores, policy backtests, and ₹ impact figures depend on assumptions and are estimates. Validate them with a controlled rollout before using them to cancel orders automatically.
- The WhatsApp simulator is local-only. A production integration would need WhatsApp Business API setup, consent handling, delivery/payment provider integration, and monitoring.
- Optional Groq use requires a working API key, network access, and a model available to that key. Local rules and cache provide the fallback.

## Project layout

```text
app/          Streamlit dashboard and interactive pages
config/       Business thresholds and WhatsApp templates
data/         Local SQLite state and committed text cache
docs/         Generated reports, decision log, and human-completed logs
engine/       Cleaning, features, model, economics, decisions, and chat flow
prompts/      Text-check prompt templates
scripts/      Pipeline, training, exploration, and backtest commands
specs/        Assignment implementation specifications
tests/        Automated regression tests
```
