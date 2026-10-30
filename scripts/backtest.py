"""Compare COD policies on out-of-fold risks and generate sensitivity results."""
from copy import deepcopy
from pathlib import Path
import numpy as np
import pandas as pd
from engine.cleaning import clean_orders, training_rows
from engine.config import Settings, load_config
from engine.decision import decide
from engine.economics import rto_cost, value_at_stake
from engine.model import train_model

TEST_MONTH = "2026-09"
POLICIES = ["ship_all", "ops_proposal", "our_rules", "rules_same_first_time_bands"]

def _orders_with_risk() -> pd.DataFrame:
    """Join cleaned labelled rows to stored out-of-fold predictions."""
    orders = training_rows(clean_orders(pd.read_csv("orders_sample.csv")))
    risk_path = Path("models/oof_predictions.csv")
    if not risk_path.exists():
        train_model(orders)
    risks = pd.read_csv(risk_path)[["order_id", "risk"]]
    return orders.merge(risks, on="order_id", validate="one_to_one")

def _ops_actions(rows: pd.DataFrame, full: pd.DataFrame) -> list[str]:
    """Apply the ops proposal using only prior-month city and state outcomes."""
    actions = []
    months = rows["order_datetime"].dt.strftime("%Y-%m")
    for (_, row), month in zip(rows.iterrows(), months):
        history = full[full["order_datetime"] < pd.Timestamp(f"{month}-01")]
        city_rate = history.groupby("city")["final_status"].apply(lambda values: (values == "RTO").mean())
        state_rate = history.groupby("state")["final_status"].apply(lambda values: (values == "RTO").mean())
        risky_geo = city_rate.get(row["city"], 0) >= .40 or state_rate.get(row["state"], 0) >= .40
        actions.append("HOLD" if float(row["risk"]) >= .50 or risky_geo else "SHIP")
    return actions

def _rule_decisions(rows: pd.DataFrame, cfg: Settings) -> list[object]:
    """Apply configured decisions to a batch of risk-scored orders."""
    return [decide(row.to_dict(), float(row["risk"]), cfg) for _, row in rows.iterrows()]

def _summarize(rows: pd.DataFrame, actions: list[str], decisions: list[object], cfg: Settings) -> dict[str, float | int | str]:
    """Combine actual ship/hold outcomes and expected intervention economics."""
    saved = lost = discount_cost = message_cost = rto_avoided = genuine_lost = 0.0
    first_time_held = 0
    cost_per_rto = rto_cost(cfg)
    for (_, row), action, decision in zip(rows.iterrows(), actions, decisions):
        actual_rto = row["final_status"] == "RTO"
        first = int(row["customer_prior_orders"] == 0)
        first_time_held += int(action == "HOLD" and first)
        if action == "HOLD":
            saved += cost_per_rto if actual_rto else 0
            lost += value_at_stake(row.to_dict(), cfg) if not actual_rto else 0
            rto_avoided += int(actual_rto)
            genuine_lost += int(not actual_rto)
        elif action in {"CONFIRM", "NUDGE"}:
            saved += decision.est_saved
            lost += decision.est_lost
            discount_cost += decision.est_discount_cost
            message_cost += decision.est_msg_cost
            rto_avoided += decision.est_saved / cost_per_rto
            genuine_lost += decision.est_lost / max(1.0, value_at_stake(row.to_dict(), cfg))
    result: dict[str, float | int | str] = {"count": len(rows), "rto_avoided": rto_avoided, "genuine_lost": genuine_lost, "saved_inr": saved, "lost_inr": lost, "discount_cost_inr": discount_cost, "message_cost_inr": message_cost, "net_inr": saved - lost - discount_cost - message_cost, "first_time_held": first_time_held}
    result.update({f"{action.lower()}_count": actions.count(action) for action in ["SHIP", "CONFIRM", "NUDGE", "HOLD"]})
    return result

def _policy_rows(rows: pd.DataFrame, full: pd.DataFrame, cfg: Settings) -> list[dict[str, float | int | str]]:
    """Calculate policy totals for held-out and full-sample periods."""
    same_bands = deepcopy(cfg.data)
    same_bands["risk_bands"]["first_time_customer"] = deepcopy(same_bands["risk_bands"]["repeat_customer"])
    same_cfg = Settings(same_bands)
    base_decisions = _rule_decisions(rows, cfg)
    same_decisions = _rule_decisions(rows, same_cfg)
    ops_actions = _ops_actions(rows, full)
    policy_actions = {
        "ship_all": ["SHIP"] * len(rows),
        "ops_proposal": ops_actions,
        "our_rules": [item.action for item in base_decisions],
        "rules_same_first_time_bands": [item.action for item in same_decisions],
    }
    results = []
    for policy in POLICIES:
        decisions = base_decisions if policy != "rules_same_first_time_bands" else same_decisions
        results.append({"policy": policy, **_summarize(rows, policy_actions[policy], decisions, cfg)})
    return results

def _sensitivity(rows: pd.DataFrame, cfg: Settings) -> pd.DataFrame:
    """Evaluate configured rules across confirmation and prepaid assumptions."""
    rows_out = []
    for catches in [.2, .4, .6]:
        for drops in [.01, .03, .08]:
            for multiplier in [.5, 1.0, 1.5]:
                data = deepcopy(cfg.data)
                data["assumptions"]["confirm_catches_share_of_returns"] = catches
                data["assumptions"]["confirm_loses_share_of_genuine"] = drops
                table = data["assumptions"]["prepaid_conversion_by_discount_pct"]
                data["assumptions"]["prepaid_conversion_by_discount_pct"] = {key: min(1.0, float(value) * multiplier) for key, value in table.items()}
                scenario = Settings(data)
                decisions = _rule_decisions(rows, scenario)
                actions = [item.action for item in decisions]
                result = _summarize(rows, actions, decisions, scenario)
                rows_out.append({"catch_share": catches, "genuine_drop_share": drops, "prepaid_conversion_multiplier": multiplier, "net_inr": result["net_inr"]})
    return pd.DataFrame(rows_out)

def main() -> None:
    """Write policy comparisons for all labelled rows and the held-out month."""
    cfg = load_config()
    full = _orders_with_risk()
    periods = {"all_months": full, "held_out_month": full[full["order_datetime"].dt.strftime("%Y-%m") == cfg["model"]["test_month"]]}
    summaries = []
    for period, rows in periods.items():
        for item in _policy_rows(rows, full, cfg):
            summaries.append({"period": period, **item})
    summary = pd.DataFrame(summaries)
    sensitivity = _sensitivity(periods["held_out_month"], cfg)
    break_even = next((rate for rate in np.linspace(0, 1, 101) if _sensitivity_with_catch(periods["held_out_month"], cfg, float(rate)) < 0), None)
    monthly_count = full.groupby(full["order_datetime"].dt.strftime("%Y-%m")).size().mean()
    scale_factor = 1650 / monthly_count
    summary["scaled_net_inr"] = summary["net_inr"] * scale_factor
    summary["scale_factor"] = scale_factor
    Path("docs").mkdir(exist_ok=True)
    summary.to_csv("docs/backtest_summary.csv", index=False)
    sensitivity.to_csv("docs/backtest_sensitivity.csv", index=False)
    summary_text = summary.to_string(index=False)
    sensitivity_text = sensitivity.to_string(index=False)
    Path("docs/backtest_summary.md").write_text("# Backtest policy comparison\n\nScaled values use the sample monthly COD count and are estimates.\n\n```text\n" + summary_text + "\n```\n\n## Sensitivity\n\n```text\n" + sensitivity_text + f"\n```\n\nBreak-even confirmation catch share: {break_even}.\n", encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Break-even confirmation catch share: {break_even}")

def _sensitivity_with_catch(rows: pd.DataFrame, cfg: Settings, catch: float) -> float:
    """Return rule-policy net impact for a single confirmation catch share."""
    data = deepcopy(cfg.data)
    data["assumptions"]["confirm_catches_share_of_returns"] = catch
    scenario = Settings(data)
    decisions = _rule_decisions(rows, scenario)
    return float(_summarize(rows, [item.action for item in decisions], decisions, scenario)["net_inr"])

if __name__ == "__main__":
    main()
