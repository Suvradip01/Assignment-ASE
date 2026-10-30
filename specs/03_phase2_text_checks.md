# Phase 2: text checks and optional LLM

## Local rules

`engine/text_rules.py` supplies address quality, fake-name and language checks. These checks must run without a network connection. Feature building always keeps the rule-based address flag and combines fake-name detection with the local rule.

## Optional provider

`engine/llm.py` supports Groq when `LLM_PROVIDER=groq`, `GROQ_API_KEY` is set, and `LLM_MODEL` names an available model. `LLM_PROVIDER=none`, a missing key, a provider error, or an invalid response uses the local rules and never raises an LLM error to the order caller.

The address/name request may contain only `customer_name`, `address`, `city`, and `state`. It returns `address_score`, `name_fake`, and `address_language`. Validate response types and ranges before accepting the result. Cache only derived features keyed by a hash of the eligible text; do not cache raw text or identifiers.

For an unclear WhatsApp reply only, `classify_reply()` may return `confirm`, `cancel`, `change_address`, `question`, or `other`. It must not make a shipping decision. Redact phone numbers and amounts before sending reply text. Keyword-parsed replies stay local. Any provider failure falls back to the parser's unclear path.

## Acceptance

- Fake clients verify successful response parsing without making network requests.
- Missing key and provider errors return local-rule results.
- Invalid output is rejected and the fallback is used.
- Cache hits avoid provider calls and contain no source text, phone, order ID, or order value.
- Tests verify the outbound payload contains only the approved address/name fields and redacted unclear-reply text.
