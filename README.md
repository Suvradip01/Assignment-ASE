# COD Order Decision Engine

## 1. Problem statement

The assignment describes a direct-to-consumer haircare business where about 55% of orders are
Cash on Delivery (COD), and about 28% of COD orders become Return to Origin (RTO). An RTO costs
an estimated ₹169.40: ₹65 forward shipping + ₹65 return shipping + ₹25 packaging and handling +
expected damage cost of 8% × ₹180. The business receives about 3,000 orders each month, has an
average order value of ₹649, a delivered-order gross margin of about 62%, and spends ₹300 or
more to acquire a new customer. Prepaid orders have an estimated 4% RTO rate.

Operations wants to reduce losses from returned orders. Marketing wants to avoid rejecting
genuine first-time customers after paying to acquire them. The system should help balance both
goals using estimated rupee impact, while keeping decisions understandable and adjustable.

## 2. Solution

This project cleans the supplied historical order data, estimates each order's RTO risk, and
applies transparent business rules to recommend one of four actions:

- **SHIP:** ship the order as-is.
- **CONFIRM:** ask the customer to confirm before dispatch.
- **NUDGE:** offer an estimated discount to encourage prepaid payment.
- **HOLD:** hold the order for review or prevent dispatch when configured rules require it.

Each recommendation includes a plain-English reason and estimated impact. First-time and repeat
customers can have different risk thresholds. Costs, thresholds, discounts, and WhatsApp timing
are editable in `config/settings.yaml` and `config/whatsapp_templates.yaml`.

The model estimates return probability from tabular order data. Python rules handle action
selection and rupee calculations so these decisions are repeatable and auditable. Optional Groq
text checks help assess messy names and addresses; Groq may also classify unclear WhatsApp
replies. It does not choose an action, probability, threshold, or discount. Common yes/no
replies are handled by a deterministic parser. The text layer falls back to local rules and
cache when no key is available or a request fails.

The WhatsApp simulator is local-only, and the dashboard labels financial impacts as estimates.
No real messages or payments are sent.

## 3. Setup and startup (Windows PowerShell)

### Prerequisites

- Windows PowerShell
- Python 3.11
- This repository, including `orders_sample.csv`
- Internet access for installing Python packages

From the repository root, create and activate a virtual environment, install dependencies, and
generate the local model, database, and reports:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m scripts.run_all
```

If PowerShell blocks activation, allow it for the current terminal only, then activate the
environment:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Start the app:

```powershell
python -m streamlit run app/Home.py
```

Open <http://localhost:8501>. Keep that terminal open while using the app. Stop Streamlit with
`Ctrl+C`.

The first `python -m scripts.run_all` run cleans `orders_sample.csv`, trains and evaluates the
risk model, scores orders into a local SQLite database, runs the backtest, and regenerates
analysis reports under `docs/`. It works without an API key. For later launches, activate
`.venv` and run only `python -m streamlit run app/Home.py` unless you need to regenerate the
model and reports.

### Optional: enable Groq for live text checks

Groq is optional; the app runs with local rules and the committed text-feature cache when it is
not configured. To enable Groq for live checks in **Try an order**, copy the example environment
file:

```powershell
Copy-Item .env.example .env
```

Open `.env` and set your own key:

```dotenv
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
LLM_MODEL=openai/gpt-oss-20b
```

Save `.env` and restart Streamlit. The Try an order page shows `groq`, `cache`, or `rules` as
the text-check source. The historical batch pipeline intentionally uses local text rules and
does not send every sample order to Groq. The LLM receives only customer name, address, city,
and state text; it never receives phone numbers, order IDs, or order values. Never commit `.env`
or share your API key.

### Run tests

With `.venv` activated, run:

```powershell
python -m pytest
```

## 4. How the system works

```text
orders_sample.csv
       |
       v
clean and validate -> text checks -> tabular risk model -> estimated RTO risk
                                                        |
                                  YAML thresholds + deterministic economics
                                                        |
                            SHIP / CONFIRM / NUDGE / HOLD + reason
                                                        |
                                     SQLite -> Streamlit dashboard

WhatsApp simulator -> message templates + reply parser -> mock conversation state
```

### App pages

- **Home:** daily action counts, estimated saved/lost/net impact, recent trends, and orders
  needing human review. If the selected date has no sample orders, it displays the latest
  available sample date.
- **Try an order:** score a manually entered order or preset and inspect its risk, action,
  explanation, flags, text-check source, and estimated action values.
- **WhatsApp simulator:** exercise confirmation and prepaid message flows, customer replies,
  reminders, and timeouts.
- **What if?:** explore how a different hold threshold changes estimated held-out policy
  results; it does not edit the saved configuration.

## 5. Change business settings

Edit `config/settings.yaml`:

- `costs`: shipping, packaging, damage, margin, acquisition, payment, and message cost
  assumptions.
- `risk_bands`: action cutoffs for first-time and repeat customers.
- `rules`: minimum order value, manual overrides, and alert levels.
- `prepaid_offer`: discount limits and customer/company savings split.
- `whatsapp`: quiet hours, reminders, timeouts, and message limits.
- `assumptions`: estimated confirmation and prepaid response behavior.
- `analysis`: backtest comparison and sensitivity scenarios.

Edit `config/whatsapp_templates.yaml` to change the mock English and Hinglish messages. Invalid
business settings raise a validation error rather than silently using defaults.

## 6. Edge cases and safeguards

- **Input data:** trims whitespace, normalizes Indian phone and pincode formats, handles missing
  city/address values, clips prior RTO counts to prior order counts, removes exact duplicate
  rows, keeps the latest duplicate order ID, and excludes unlabeled `IN_TRANSIT` rows from
  training.
- **Unsafe or incomplete orders:** invalid or zero order values are held. Missing required
  fields receive a safe `CONFIRM` result with a missing-field reason. Invalid phone numbers,
  suspicious names, incomplete addresses, and blocked or prepaid-only pincodes are represented
  by flags or configured rules.
- **Model and text checks:** categorical values can include unseen cities, states, and pincode
  prefixes. Text checks use a committed cache or local rules when Groq is unavailable, and do
  not send phone numbers, order IDs, or order values.
- **WhatsApp replies:** common English/Hinglish replies are handled by the parser. Duplicate
  inbound message IDs are ignored; unclear replies can be sent for classification and otherwise
  go through clarification or human review. Quiet hours, reminders, no-reply timeouts, and STOP
  are represented in the simulator.
- **Dashboard:** empty dates fall back to the latest sample date; metrics guard against empty
  counts. Financial impact remains labeled as estimated.

## 7. Reports and project records

The pipeline generates or updates:

- [`docs/data_quality.md`](docs/data_quality.md): cleaning and data quality summary.
- [`docs/findings.md`](docs/findings.md): segment findings from the sample.
- [`docs/backtest_summary.md`](docs/backtest_summary.md): policy comparison and sensitivity
  analysis.
- [`docs/discount_table.md`](docs/discount_table.md): discount economics.
- [`docs/memo_numbers.md`](docs/memo_numbers.md): generated figures to use in the founder memo.
- [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md): implementation choices and rationale.

These results are based on a small historical sample and configured assumptions. Estimated
impact is not measured business savings or losses.

## 8. Known limits

- The supplied dataset is a small historical sample and may not represent current customer
  behavior or full monthly order volume.
- Risk scores and policy impact depend on model performance and assumptions. Validate with a
  controlled rollout before using HOLD to cancel orders automatically.
- The WhatsApp simulator is a mock. Production use would need WhatsApp Business API setup,
  consent handling, delivery/payment integration, and operational monitoring.
- Groq requires a valid key, network access, and model access. Local rules and cache provide the
  fallback.

## 9. Project layout

```text
app/          Streamlit dashboard and interactive pages
config/       Business settings and WhatsApp templates
data/         Local SQLite state and committed text cache
docs/         Generated reports, decision log, and human-completed logs
engine/       Cleaning, features, model, economics, decisions, and chat flow
prompts/      Text-check prompt templates
scripts/      Pipeline, training, exploration, and backtest commands
specs/        Assignment implementation specifications
tests/        Automated regression tests
```
