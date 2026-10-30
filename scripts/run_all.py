"""Run the complete local pipeline without an API key."""

from pathlib import Path
import sqlite3
import pandas as pd
from engine.cleaning import clean_orders, training_rows
from engine.config import Settings, load_config
from engine.features import build_features
from engine.model import train_model, load_model
from engine.decision import Decision, decide
from engine.reasons import build_reason
from engine.store import connect
from scripts.explore import main as explore
from scripts.backtest import main as backtest
from scripts.memo_numbers import main as memo


def _upsert_decision(
    db: sqlite3.Connection, decision: Decision, record: dict[str, object]
) -> None:
    """Insert or update a scored order in the local decision database."""
    db.execute(
        "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(order_id) DO UPDATE SET action=excluded.action, "
        "risk=excluded.risk, reason=excluded.reason, "
        "discount_inr=excluded.discount_inr, est_saved=excluded.est_saved, "
        "est_lost=excluded.est_lost, est_discount_cost=excluded.est_discount_cost, "
        "est_msg_cost=excluded.est_msg_cost, order_date=excluded.order_date, "
        "is_first_time=excluded.is_first_time, order_value=excluded.order_value, "
        "state=excluded.state, city=excluded.city, llm_source=excluded.llm_source, "
        "decided_at=excluded.decided_at",
        (
            decision.order_id,
            decision.action,
            decision.risk,
            decision.reason,
            decision.discount_inr,
            decision.est_saved,
            decision.est_lost,
            decision.est_discount_cost,
            decision.est_msg_cost,
            str(record.get("order_datetime", "")),
            int(record.get("is_first_time", 0)),
            float(record.get("order_value", 0)),
            record.get("state", ""),
            record.get("city", ""),
            record.get("llm_source", "rules"),
            decision.decided_at,
        ),
    )


def _save_order_decision(
    db: sqlite3.Connection, record: dict[str, object], risk: float, cfg: Settings
) -> None:
    """Apply policy to one feature record and save the result."""
    decision = decide(
        record,
        risk,
        cfg,
        {"address_score": record["address_score"], "name_fake": record["name_fake"]},
    )
    with_reason = decision.__class__(
        **{**decision.__dict__, "reason": build_reason(decision, record)}
    )
    _upsert_decision(db, with_reason, record)


def _score_orders(cleaned: pd.DataFrame, cfg: Settings) -> int:
    """Score cleaned orders with the saved model and persist decisions."""
    bundle = load_model()
    feat = build_features(cleaned, value_edges=bundle.get("value_edges"))
    risks = bundle["model"].predict_proba(feat[bundle["columns"]])[:, 1]
    db = connect()
    for (_, row), risk in zip(feat.iterrows(), risks, strict=True):
        _save_order_decision(db, row.to_dict(), float(risk), cfg)
    db.commit()
    db.close()
    return len(feat)


def main() -> None:
    """Clean, train, analyze, score into SQLite, and generate reports."""
    cfg = load_config()
    cleaned = clean_orders(pd.read_csv("orders_sample.csv"))
    explore()
    train_model(training_rows(cleaned))
    backtest()
    order_count = _score_orders(cleaned, cfg)
    memo()
    print(f"Pipeline complete: {order_count} orders scored; reports written to docs/.")


if __name__ == "__main__":
    main()
