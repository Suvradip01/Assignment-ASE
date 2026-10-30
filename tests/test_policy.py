"""Boundary, economics and configuration validation checks."""

from pathlib import Path
import pandas as pd
import pytest
from engine.config import load_config, config_hash
from engine.decision import decide
from engine.economics import discount, ev_confirm, ev_nudge, ev_ship, rto_cost
from engine.metrics import dashboard_aggregates


def _valid_order() -> dict[str, object]:
    """Return a complete valid order fixture for decision tests."""
    return {
        "order_id": "P1",
        "order_datetime": "2026-10-30",
        "customer_name": "Asha Sharma",
        "phone": "9876543210",
        "address": "12 Main Road",
        "city": "Delhi",
        "state": "Delhi",
        "pincode": "110001",
        "order_value": 649,
        "num_items": 1,
        "items": "Shampoo",
        "customer_prior_orders": 1,
        "customer_prior_rto": 0,
        "utm_source": "test",
        "phone_valid": 1,
        "address_score": 0.9,
    }


def test_economic_examples_and_actions() -> None:
    """Keep core cost and expected-value calculations finite and consistent."""
    cfg = load_config()
    order = _valid_order()
    assert rto_cost(cfg) == pytest.approx(169.4)
    assert discount(0.5, order, cfg) == pytest.approx(30)
    assert ev_ship(0.3, order, cfg) != ev_confirm(0.3, order, cfg)
    assert ev_nudge(0.5, order, cfg) > 0


def test_risk_boundaries_and_customer_bands() -> None:
    """Apply exact threshold boundaries to the higher-risk action."""
    cfg = load_config()
    repeat = _valid_order()
    assert decide(repeat, 0.199, cfg).action == "SHIP"
    assert decide(repeat, 0.20, cfg).action == "CONFIRM"
    assert decide(repeat, 0.35, cfg).action == "NUDGE"
    assert decide(repeat, 0.80, cfg).action == "HOLD"
    first = {**repeat, "customer_prior_orders": 0}
    assert decide(first, 0.82, cfg).action == "NUDGE"
    assert decide(first, 0.85, cfg).action == "HOLD"


def test_nonviable_discount_downgrades_nudge() -> None:
    """Skip prepaid when configured economics leave no viable discount."""
    cfg = load_config()
    cfg.data["costs"]["payment_gateway_fee_pct"] = 1.0
    result = decide(_valid_order(), 0.4, cfg)
    assert result.action == "CONFIRM" and "discount_not_viable" in result.flags


def test_config_rejects_bad_risk_and_hash_tracks_file(tmp_path: Path) -> None:
    """Reject invalid threshold probabilities and hash configuration bytes."""
    source = Path("config/settings.yaml").read_text(encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        source.replace("ship_below: 0.25", "ship_below: 1.25", 1), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="must be between 0 and 1"):
        load_config(bad)
    path = tmp_path / "hash.yaml"
    path.write_text(source, encoding="utf-8")
    before = config_hash(path)
    path.write_text(source + "\n# changed\n", encoding="utf-8")
    assert config_hash(path) != before


def test_empty_dashboard_has_all_buckets() -> None:
    """Return zero-safe totals with all action buckets for an empty date."""
    result = dashboard_aggregates(
        pd.DataFrame(
            columns=[
                "action",
                "est_saved",
                "est_lost",
                "est_discount_cost",
                "est_msg_cost",
            ]
        )
    )
    assert result["n"] == 0 and result["net"] == 0
    assert result["counts"] == {"SHIP": 0, "CONFIRM": 0, "NUDGE": 0, "HOLD": 0}
