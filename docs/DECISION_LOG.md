# Decision log

- **Missing phase 2 spec:** implemented the overview/phase 9-required text rules and optional cache-backed enrichment as the smallest behavior consistent with the other specs; alternatives were inventing elaborate undocumented interfaces or skipping the layer.
- **Hybrid ML + text checks:** model estimates risk from tabular data; optional text layer checks address/name, since those need language understanding and rules still provide a no-key fallback.
- **Model selection:** tuned logistic regression and compared it with a small gradient-boosted model using cross-validation; prefer logistic unless boosting clears the configured AUC gain without worse log loss.
- **Courier excluded:** it may be unknown before dispatch and can leak post-decision information.
- **Time features excluded:** configuration says the signal looked noisy.
- **No class weights:** probability calibration matters for ₹ calculations.
- **YAML bands + EV helper:** thresholds remain editable and explainable instead of hidden in model code.
- **Higher first-time HOLD bar:** protects acquisition cost.
- **Discount rule:** share of net savings with the configured ceiling and minimum viability floor.
- **No-reply policy:** timeout behavior uses the configured risk threshold.
- **Keyword parser first:** common replies are cheap and deterministic; optional model classification is reserved for unclear text.
- **LLM privacy:** only name/address/city/state are eligible text fields; order identifiers, phone, and order values are excluded.
- **LLM provider choice:** use Groq as the optional SDK and keep local rules as the no-key fallback; this follows the request to use Groq while keeping the dependency stack to one LLM SDK.
- **Cache committed:** no-key startup works with a deterministic local fallback.
- **Scale:** sample coverage is smaller than actual COD volume; scaled results must be labeled estimates.
- **Delivered margin:** assumed to already include shipping because the brief is ambiguous.
- **Damage cost:** applied once per RTO.
- **Assignment title:** PDF title references AI Automation Engineer while the supplied role context says Associate Software Engineer.
