"""Small offline smoke test for training artifacts and unseen categories."""

from pathlib import Path
import pandas as pd
from engine.cleaning import clean_orders, training_rows
from engine.features import build_features
from engine.model import load_model, train_model


def test_train_model_writes_diagnostics_and_scores_unseen_categories(
    tmp_path: Path,
) -> None:
    """Train on synthetic rows and verify the operational model outputs."""
    rows = []
    for index in range(200):
        rows.append(
            {
                "order_id": f"S{index}",
                "order_datetime": f"2026-{(index % 8) + 1:02d}-15",
                "customer_name": f"Customer {index}",
                "phone": f"987654{index:04d}",
                "address": f"{index} Example Road",
                "city": ["Delhi", "Jaipur", "Pune"][index % 3],
                "state": ["Delhi", "Rajasthan", "Maharashtra"][index % 3],
                "pincode": ["110001", "302001", "400001"][index % 3],
                "order_value": 349 + index % 700,
                "num_items": 1 + index % 3,
                "items": "Shampoo",
                "customer_prior_orders": index % 4,
                "customer_prior_rto": index % 2,
                "utm_source": ["meta", "search"][index % 2],
                "final_status": "RTO" if index % 4 == 0 else "DELIVERED",
            }
        )
    labeled = training_rows(clean_orders(pd.DataFrame(rows)))
    metrics = train_model(labeled, tmp_path)
    assert 0 <= metrics["cv_auc"] <= 1
    assert {
        "model.joblib",
        "metrics.json",
        "calibration.csv",
        "oof_predictions.csv",
        "ablation.csv",
        "pincode_stats.csv",
    } <= {path.name for path in tmp_path.iterdir()}
    bundle = load_model(tmp_path / "model.joblib")
    unseen = pd.DataFrame(
        [
            {
                "order_id": "NEW",
                "order_datetime": "2026-10-01",
                "customer_name": "New Customer",
                "phone": "9876543210",
                "address": "1 New Road",
                "city": "Unknown City",
                "state": "Unknown State",
                "pincode": "999999",
                "order_value": 649,
                "num_items": 1,
                "items": "Shampoo",
                "customer_prior_orders": 1,
                "customer_prior_rto": 0,
                "utm_source": "new_source",
            }
        ]
    )
    features = build_features(clean_orders(unseen), value_edges=bundle["value_edges"])
    probability = bundle["model"].predict_proba(features[bundle["columns"]])[:, 1]
    assert len(probability) == 1 and 0 <= probability[0] <= 1
