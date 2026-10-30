"""Produce the prepaid offer calculation table."""

from pathlib import Path
import pandas as pd
from engine.config import load_config
from engine.economics import (
    discount,
    net_saving,
    value_at_stake,
    prepaid_rto,
    conversion_rate,
)


def main() -> None:
    """Write discount values over requested order values and risks."""
    cfg = load_config()
    rows = []
    for value in [349, 649, 1198]:
        for risk in [0.3, 0.4, 0.5, 0.7]:
            order = {"order_value": value, "customer_prior_orders": 1}
            d = discount(risk, order, cfg)
            pct = d / value * 100
            rows.append(
                {
                    "aov": value,
                    "risk": risk,
                    "saving": net_saving(risk, order, cfg),
                    "discount": d,
                    "customer_benefit_pct": pct,
                    "prepaid_rto": prepaid_rto(risk, cfg),
                    "company_net_per_conversion": net_saving(risk, order, cfg) - d,
                    "expected_conversion": conversion_rate(risk, pct, cfg),
                }
            )
    table = pd.DataFrame(rows)
    table.to_csv("docs/discount_table.csv", index=False)
    Path("docs").mkdir(exist_ok=True)
    Path("docs/discount_table.md").write_text(
        "# Discount calculations\n\n" + table.to_csv(index=False), encoding="utf-8"
    )
    sweep = []
    order = {"order_value": 649, "customer_prior_orders": 1}
    for amount in range(0, 81, 5):
        conv = conversion_rate(0.5, amount / order["order_value"] * 100, cfg)
        saving = net_saving(0.5, order, cfg)
        sweep.append(
            {
                "discount": amount,
                "conversion": conv,
                "expected_net": conv * (saving - amount),
            }
        )
    pd.DataFrame(sweep).to_csv("docs/discount_sweep.csv", index=False)
    print(table.to_string(index=False))
    print(pd.DataFrame(sweep).to_string(index=False))


if __name__ == "__main__":
    main()
