# COD Order Decision Engine

Scores COD orders and recommends SHIP, CONFIRM, NUDGE, or HOLD with a clear reason.
The model estimates return risk; transparent rules choose actions and estimate ₹ impact.
WhatsApp and the dashboard are local mockups for review.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m scripts.run_all
python -m streamlit run app/Home.py
```

Open `http://localhost:8501`. Stop Streamlit with `Ctrl+C` in that terminal. Run tests separately with `python -m pytest`.

## Architecture

```text
CSV -> clean_orders -> text checks -> feature builder -> calibrated model
                                                    -> risk bands + ₹ rules -> SQLite -> Streamlit
WhatsApp simulator -> keyword parser -> conversation state
```

## Edit thresholds

Edit `config/settings.yaml`: `costs` contains unit economics, `risk_bands` sets action cutoffs separately for new and repeat customers, `rules` contains overrides and alerts, `prepaid_offer` controls discount math, `whatsapp` controls timing, and `assumptions` contains launch estimates. Invalid values stop startup with a plain-language error.

The model estimates return probability. Plain Python and YAML handle costs, thresholds, discounts, reasons, and actions so those decisions stay repeatable and auditable. Text rules run without an API key. Copy `.env.example` to `.env`, then set `LLM_PROVIDER=groq` and `GROQ_API_KEY` for optional Groq text enrichment; `LLM_PROVIDER=none` uses local rules. The LLM receives only name, address, city, and state text, never phone numbers or order values.

## Tests and limits

Run `python -m pytest`. Sample data is small and historical; impact values are estimates, not measured savings. The WhatsApp flow is a local mock and sends no messages.

## Folder map

`engine/` contains cleaning, features, model, economics and policy code; `scripts/` contains repeatable reports; `app/` contains the dashboard and simulators; `specs/` contains the assignment requirements; `docs/` contains generated analysis and decision records.
