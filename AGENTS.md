# AGENTS.md

Project: COD Order Decision Engine. The full specification is split into files in `spec/`. Start with `spec/00_overview.md` and `spec/01_config.md`, then build one phase file at a time in numeric order.

## How to work
1. Build the phases in `spec/02_phase1_data.md` to `spec/08_phase7_backtest_memo.md`, in order. Finish with `spec/09_docs_tests_done.md`.
2. After each phase: run `pytest` and the phase's acceptance command. Fix failures before moving on.
3. Commit after each phase with a clear message.
4. If the spec is ambiguous, pick the simplest option and add a bullet to `docs/DECISION_LOG.md` (what, alternatives, why).

## Code style
- Python 3.11. Type hints on all functions. One-line docstrings.
- Small functions (about 40 lines max). Plain functions over classes; dataclasses for data.
- No magic numbers: costs, thresholds and rates come from `config/settings.yaml`.
- No `datetime.now()` inside logic; pass `now` in.
- Use `logging`, not `print`, outside script summaries.
- One shared `clean_orders()` for training and serving.

## Hard rules
- The LLM only produces text-derived features and classifies unclear WhatsApp replies. It never outputs a risk probability, a threshold, a discount or an action.
- The system must run with no API key (rule fallback + committed `data/llm_cache.jsonl`). Never raise an LLM error to the caller.
- Never commit secrets. Never send phone numbers or order values to the LLM.
- Every number that appears in `docs/` must be produced by a script. Never type results by hand.
- Do NOT write the business memo. Do NOT write entries in `docs/AI_USAGE_LOG.md` (the human does).
- Do not add frameworks beyond the stack in `spec/00_overview.md`.
- Dashboard ₹ figures are estimates and must be labelled as such.

## Commands
```
pip install -r requirements.txt
python -m scripts.run_all
streamlit run app/Home.py
pytest
```
