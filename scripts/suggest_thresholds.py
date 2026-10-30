"""Sweep configured expected value and print editable risk bands."""
import pandas as pd
from engine.cleaning import clean_orders, training_rows
from engine.config import load_config
from engine.economics import ev_confirm, ev_nudge, ev_ship

def _cutoffs(order: dict[str, float | int], cfg: object) -> tuple[float, float, float]:
    """Find expected-value cutoffs for SHIP, NUDGE and HOLD."""
    grid = [step / 100 for step in range(101)]
    ship_below = next((risk for risk in grid if ev_confirm(risk, order, cfg) > ev_ship(risk, order, cfg)), 1.0)
    nudge_from = next((risk for risk in grid if ev_nudge(risk, order, cfg) - ev_confirm(risk, order, cfg) >= 10), 1.0)
    hold_at = next((risk for risk in grid if ev_confirm(risk, order, cfg) < 0), 1.0)
    return ship_below, nudge_from, hold_at

def main() -> None:
    """Print cutoffs and per-action expected values for each customer type."""
    cfg = load_config()
    clean = training_rows(clean_orders(pd.read_csv("orders_sample.csv")))
    average_value = float(clean["order_value"].mean())
    bands = {}
    for label, prior_orders in [("first_time_customer", 0), ("repeat_customer", 1)]:
        order = {"order_value": average_value, "customer_prior_orders": prior_orders}
        bands[label] = _cutoffs(order, cfg)
    print("Suggested risk bands from configured expected value:")
    for label, (ship_below, nudge_from, hold_at) in bands.items():
        print(f"{label}: ship_below={ship_below:.2f}, nudge_from={nudge_from:.2f}, hold_at_or_above={hold_at:.2f}")
    print("\nReady-to-review YAML (the script does not edit settings.yaml):")
    for label, (ship_below, nudge_from, hold_at) in bands.items():
        print(f"{label}: {{ship_below: {ship_below:.2f}, nudge_from: {nudge_from:.2f}, hold_at_or_above: {hold_at:.2f}}}")
    print("\nExpected values by risk:")
    for label, prior_orders in [("first_time_customer", 0), ("repeat_customer", 1)]:
        order = {"order_value": average_value, "customer_prior_orders": prior_orders}
        for step in range(1, 10):
            risk = step / 10
            print(f"{label} risk={risk:.1f} ship={ev_ship(risk, order, cfg):.2f} confirm={ev_confirm(risk, order, cfg):.2f} nudge={ev_nudge(risk, order, cfg):.2f}")

if __name__ == "__main__":
    main()
