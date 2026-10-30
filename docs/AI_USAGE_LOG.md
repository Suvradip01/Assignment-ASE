# AI usage log

| Tool | Task | Outcome |
|---|---|---|
| OpenAI Codex | Implemented and refined the decision engine, Streamlit pages, documentation, and submission artifacts. | Reviewed changes against the assignment and project requirements; the project test suite passed during development. |
| Groq (`openai/gpt-oss-20b`, configured through `.env`) | Live order text checks for text-derived address/name features. The model does not set risk probabilities, actions, thresholds, or discounts. | The app displayed `Text check source: groq` on a successful live check. Invalid provider JSON was observed to fall back to rules. |

### AI got this wrong / how I caught it / fix

- Codex suggested using `DataFrame.itertuples()` with `.to_dict()` in the What if page. The app raised an `AttributeError` when opened. I used the traceback to find the mismatch and changed the page to iterate rows as dictionaries; the page then rendered correctly.

### AI got this wrong / how I caught it / fix

- Codex initially treated the 100% local-rule share in batch scoring as a possible Groq outage. I checked the pipeline and confirmed batch scoring is intentionally local and deterministic. I removed the misleading availability warning from the batch dashboard; live order checks still report their own source.

### AI got this wrong / how I caught it / fix

- An earlier generated HOLD explanation rendered currency as `?` in the app. I checked the displayed text, corrected rupee formatting and clarified the estimated amounts, then verified the rendered result. The memo PDF was also rendered and visually checked to catch and fix an initial currency-font and month-label issue.
