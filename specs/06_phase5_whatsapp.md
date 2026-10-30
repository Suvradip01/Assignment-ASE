# Phase 5: WhatsApp flow (mock)

> Read `00_overview.md` and `01_config.md` first. Finish this phase (tests + acceptance command) before starting the next.


Pure Python in `engine/whatsapp/`. State persisted in SQLite. No real WhatsApp.

### Templates (`config/whatsapp_templates.yaml`, English + Hinglish)
Keys: `confirm_cod`, `confirm_address`, `nudge_prepaid`, `nudge_prepaid_only`, `reminder`, `payment_link`, `payment_reminder`, `confirmed_ack`, `prepaid_ack`, `cancelled_ack`, `clarify`, `address_received`, `no_reply_cancelled`, `human_handoff`, `opt_out_ack`, `reopened_ack`. Placeholders: `{first_name} {brand} {order_id} {items} {order_value} {address_short} {city} {pincode} {discount} {prepaid_total}`. Quick-reply buttons are listed with each template.

Core messages (Codex writes the rest in the same style, short, warm, no fake urgency, no threats):

- **confirm_cod (EN):** "Hi {first_name}! Thanks for ordering from {brand} 💛 Order #{order_id}: {items}, ₹{order_value} (Cash on Delivery). Ship to: {address_short}, {city} {pincode}. Please confirm so we can dispatch." Buttons: `Yes, confirm` / `No, cancel`.
- **confirm_cod (Hinglish):** "Hi {first_name}! {brand} se order karne ke liye shukriya 💛 Order #{order_id}: {items}, ₹{order_value} (Cash on Delivery). Pata: {address_short}, {city} {pincode}. Dispatch ke liye 'Haan' bhejein, cancel ke liye 'Nahi'."
- **confirm_address:** same intro, then "Humein aapka poora address chahiye (ghar/flat number, area, landmark). Please reply with the full address." (EN version too.)
- **nudge_prepaid (EN):** "Hi {first_name}! Your {brand} order #{order_id} is ready. Pay online now and get ₹{discount} off: pay ₹{prepaid_total} instead of ₹{order_value}." Buttons: `Pay online & save ₹{discount}` / `Keep Cash on Delivery` / `Cancel order`.
- **nudge_prepaid (Hinglish):** "Hi {first_name}! Aapka {brand} order #{order_id} ready hai. Abhi online pay karein aur ₹{discount} off paayein: ₹{order_value} ki jagah ₹{prepaid_total}." Same buttons.
- `nudge_prepaid_only`: same but only `Pay online` / `Cancel order`.

**Language:** Hinglish if the LLM/rules `address_language` is hinglish/hindi OR state in `hinglish_states`; else English. If the customer's reply is Hinglish, switch to Hinglish for later messages.

**Timing:**
- Send within 10 minutes of the decision, but never inside quiet hours (21:00–09:00 IST). Orders decided in quiet hours are queued to 09:00 and the 24 h clock starts at the actual send time.
- Reminder once at +4 h (only if inside allowed hours, else at next 09:00).
- Timeout at +24 h after send.
- Max 4 outbound messages per order.

### `parser.py` → `parse_reply(text, state) -> Intent`
Intents: `YES, NO, PAY, KEEP_COD, CANCEL, STOP, ADDRESS, UNCLEAR`. Pure code first:
- Normalise: lower-case, strip punctuation and emoji, collapse spaces. Button payloads map directly to intents.
- YES: `yes y yeah ok okay confirm confirmed haan ha han haa theek hai thik hai kar do bhej do 👍 1`. NO/CANCEL: `no n nahi nahin nhi cancel cancel kardo mat bhejo nahi chahiye 👎 2`.
- **Meaning depends on state:** in the CONFIRM flow YES = confirm, NO = cancel. In the NUDGE flow YES = pay online, NO = keep COD (not cancel), and only the explicit word "cancel" / button cancels.
- Both YES and NO tokens in one message ("no problem, haan bhej do") → UNCLEAR → LLM.
- `STOP / unsubscribe / band karo messages` → STOP.
- In `confirm_address` state, any message with ≥ 10 characters containing a digit or locality word → ADDRESS.
- Everything else → UNCLEAR. For UNCLEAR only, call the LLM (`prompts/reply_intent.txt`) to classify into `confirm | cancel | change_address | question | other`; on any LLM failure → UNCLEAR. The LLM never triggers shipping directly on a `question`/`other`.

### `flow.py` (state machine)
States: `QUEUED, AWAITING_CONFIRMATION, AWAITING_PREPAID_CHOICE, AWAITING_ADDRESS, AWAITING_PAYMENT, CONFIRMED_SHIP_COD, PAID_SHIP_PREPAID, CANCELLED_BY_CUSTOMER, AUTO_SHIPPED_NO_REPLY, CANCELLED_NO_REPLY, NEEDS_HUMAN, OPTED_OUT`.

API (all take `now`):
- `start_conversation(decision, order, now) -> (Conversation, [Outbound])`
- `handle_inbound(conv, text, msg_id, now) -> (Conversation, [Outbound])`
- `tick(conv, now) -> (Conversation, [Outbound])`   # reminders, queue release, timeouts

**Behaviour table:**

| Situation | Result |
|---|---|
| CONFIRM: "yes/haan" | `confirmed_ack`, state `CONFIRMED_SHIP_COD` |
| CONFIRM: "no/nahi" | `cancelled_ack`, `CANCELLED_BY_CUSTOMER` |
| NUDGE: pay / "yes" | send mock payment link, `AWAITING_PAYMENT`; "Pay" simulated by a button |
| NUDGE: keep COD / "no" | counts as confirmation → `CONFIRMED_SHIP_COD` |
| NUDGE: cancel | `CANCELLED_BY_CUSTOMER` |
| AWAITING_PAYMENT, link unpaid after 12 h | one `payment_reminder`; then fall back to the COD confirm question (unless prepaid-only → no-reply rule) |
| Random / unclear text | `clarify` message (shows the options again). After `max_clarification_messages` unclear replies → `NEEDS_HUMAN` + `human_handoff` |
| Customer sends a new address | store it as `address_update`, re-run address check, send `address_received`; if score now ≥ junk threshold → treated as confirmation of the order, else `NEEDS_HUMAN` |
| No reply by +4 h | one reminder |
| No reply by +24 h, risk **< 0.50** | `AUTO_SHIPPED_NO_REPLY` (cheaper to risk shipping than to lose a real customer) |
| No reply by +24 h, risk **≥ 0.50** | `CANCELLED_NO_REPLY` + `no_reply_cancelled` message ("reply any time in 7 days to reopen") |
| No reply, address was junk (`confirm_address`) | `NEEDS_HUMAN` (cannot ship to a junk address) |
| Reply after cancel, within 7 days | `reopened_ack`, back to `AWAITING_CONFIRMATION` once |
| Reply after cancel, > 7 days | `human_handoff`, `NEEDS_HUMAN` |
| "STOP" | `opt_out_ack`, `OPTED_OUT`, no more messages ever for this phone, `NEEDS_HUMAN` for the order |
| Same inbound `msg_id` twice | processed once (idempotent; unique constraint) |
| Reply to an already finished conversation | ignored politely, logged |
| Voice note / image / empty text | treated as UNCLEAR |
| Message cap reached | no further outbound; `NEEDS_HUMAN` |

### Simulator page: `app/pages/2_WhatsApp_simulator.py`
Pick an order from the CONFIRM/NUDGE decisions, see the chat bubbles, quick-reply buttons, a free-text box, and a **"Advance time" control (+4 h, +24 h, +48 h)** that calls `tick`. Show current state, event log, and the final ₹ outcome label. A visible "MOCK, nothing is sent" banner.

**Acceptance:** tests drive each row of the table using an injected clock: yes, no, nudge-pay, nudge-keep-COD, random ×3, silence 4 h / 24 h at risk 0.3 and 0.7, quiet-hours queueing, duplicate msg_id, STOP, late reply, address reply, LLM-intent failure fallback.
