"""Train, evaluate, save and load calibrated return-risk models."""

from pathlib import Path
from typing import Any
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    log_loss,
    brier_score_loss,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from engine.config import load_config
from engine.features import build_features, model_columns

RANDOM_SEED = 42
FOLDS = 5
SMOOTHING = 20
FEATURE_GROUPS = {
    "geography": ["state", "city", "pin3", "pincode_missing", "pin_state_mismatch"],
    "customer_history": [
        "is_first_time",
        "customer_prior_orders",
        "customer_prior_rto",
        "prior_rto_rate",
    ],
    "text": ["address_score", "address_junk_rule", "name_fake", "address_has_digit"],
    "value": ["value_bin"],
    "source": ["utm_source"],
    "courier": ["courier"],
    "time": ["hour", "weekday"],
}


def _pipeline(data: pd.DataFrame, kind: str = "logistic", c: float = 1.0) -> Pipeline:
    """Create a preprocessing and classifier pipeline."""
    columns = list(data.columns)
    categories = [
        name
        for name in ["state", "city", "pin3", "value_bin", "utm_source"]
        if name in columns
    ]
    numeric = [name for name in columns if name not in categories]
    encoder = OneHotEncoder(
        handle_unknown="ignore", min_frequency=10, sparse_output=False
    )
    prep = ColumnTransformer(
        [
            ("cat", encoder, categories),
            (
                "num",
                Pipeline(
                    [
                        (
                            "impute",
                            SimpleImputer(strategy="median", add_indicator=True),
                        ),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            ),
        ]
    )
    classifier = (
        LogisticRegression(C=c, max_iter=1000, random_state=RANDOM_SEED)
        if kind == "logistic"
        else HistGradientBoostingClassifier(
            max_depth=3, max_iter=150, early_stopping=True, random_state=RANDOM_SEED
        )
    )
    return Pipeline([("prep", prep), ("model", classifier)])


def _probability_metrics(
    y: pd.Series, prediction: np.ndarray, prefix: str = ""
) -> dict[str, float]:
    """Return discrimination and probability quality metrics."""
    return {
        f"{prefix}auc": float(roc_auc_score(y, prediction)),
        f"{prefix}pr_auc": float(average_precision_score(y, prediction)),
        f"{prefix}log_loss": float(log_loss(y, np.clip(prediction, 0.001, 0.999))),
        f"{prefix}brier": float(brier_score_loss(y, prediction)),
    }


def _select_model(
    X: pd.DataFrame, y: pd.Series, folds: StratifiedKFold
) -> tuple[Pipeline, dict[str, float]]:
    """Tune logistic C and select boosting only when its CV gain is material."""
    search = GridSearchCV(
        _pipeline(X), {"model__C": [0.1, 0.3, 1, 3]}, scoring="roc_auc", cv=folds
    )
    search.fit(X, y)
    logistic = search.best_estimator_
    logistic_oof = cross_val_predict(logistic, X, y, cv=folds, method="predict_proba")[
        :, 1
    ]
    boosting = _pipeline(X, kind="boosting")
    boosting_oof = cross_val_predict(boosting, X, y, cv=folds, method="predict_proba")[
        :, 1
    ]
    logistic_metrics = _probability_metrics(y, logistic_oof)
    boosting_metrics = _probability_metrics(y, boosting_oof)
    choose_boost = (
        boosting_metrics["auc"] > logistic_metrics["auc"] + 0.02
        and boosting_metrics["log_loss"] <= logistic_metrics["log_loss"]
    )
    selected = boosting if choose_boost else logistic
    comparison = {f"logistic_{key}": value for key, value in logistic_metrics.items()}
    comparison.update(
        {f"boosting_{key}": value for key, value in boosting_metrics.items()}
    )
    comparison["selected_boosting"] = float(choose_boost)
    comparison["logistic_c"] = float(search.best_params_["model__C"])
    return selected, comparison


def _calibrated_oof(
    estimator: Pipeline, X: pd.DataFrame, y: pd.Series, folds: StratifiedKFold
) -> np.ndarray:
    """Produce out-of-fold calibrated probabilities without fitting on held-out labels."""
    calibrated = CalibratedClassifierCV(estimator=estimator, method="sigmoid", cv=folds)
    return cross_val_predict(calibrated, X, y, cv=folds, method="predict_proba")[:, 1]


def _ablation(
    estimator: Pipeline,
    X: pd.DataFrame,
    y: pd.Series,
    folds: StratifiedKFold,
    baseline_auc: float,
    baseline_loss: float,
) -> pd.DataFrame:
    """Measure cross-validated metric changes after removing feature groups."""
    rows = []
    for group, columns in FEATURE_GROUPS.items():
        drop = [name for name in columns if name in X.columns]
        reduced = X.drop(columns=drop)
        classifier = estimator.named_steps["model"]
        kind = (
            "boosting"
            if isinstance(classifier, HistGradientBoostingClassifier)
            else "logistic"
        )
        c = float(classifier.C) if kind == "logistic" else 1.0
        prediction = _calibrated_oof(_pipeline(reduced, kind, c), reduced, y, folds)
        rows.append(
            {
                "group": group,
                "delta_auc": baseline_auc - roc_auc_score(y, prediction),
                "delta_log_loss": log_loss(y, np.clip(prediction, 0.001, 0.999))
                - baseline_loss,
            }
        )
    return pd.DataFrame(rows)


def _save_pincode_stats(feat: pd.DataFrame, y: pd.Series, root: Path) -> None:
    """Save smoothed state, pin3 and pincode return rates for operations views."""
    work = feat[["state", "pin3", "pincode"]].copy()
    work["returned"] = y.to_numpy()
    global_rate = float(y.mean())
    states = work.groupby("state")["returned"].agg(["count", "sum", "mean"])
    state_rate = {
        name: (row["sum"] + SMOOTHING * global_rate) / (row["count"] + SMOOTHING)
        for name, row in states.iterrows()
    }
    parents = work.groupby(["state", "pin3"])["returned"].agg(["count", "sum"])
    pin3_rate = {
        (state, pin3): (row["sum"] + SMOOTHING * state_rate[state])
        / (row["count"] + SMOOTHING)
        for (state, pin3), row in parents.iterrows()
    }
    rows = []
    for key, group in work.groupby(["state", "pin3", "pincode"], dropna=False):
        state, pin3, pin = key
        n, returned = len(group), int(group["returned"].sum())
        parent = pin3_rate.get((state, pin3), state_rate.get(state, global_rate))
        rate = (returned + SMOOTHING * parent) / (n + SMOOTHING)
        rows.append(
            {
                "state": state,
                "pin3": pin3,
                "pincode": pin,
                "n": n,
                "returned": returned,
                "smoothed_rate": rate,
            }
        )
    pd.DataFrame(rows).to_csv(root / "pincode_stats.csv", index=False)


def _base_training_metrics(
    y: pd.Series, oof: np.ndarray, comparison: dict[str, float]
) -> dict[str, float]:
    """Combine calibrated cross-validation scores and model comparison results."""
    metrics = _probability_metrics(y, oof, "cv_")
    metrics.update(
        {
            "top_20pct_rto_capture": float(
                y.iloc[np.argsort(oof)[-max(1, len(y) // 5) :]].sum() / y.sum()
            ),
            "n": len(y),
            "positive_rate": float(y.mean()),
            "seed": RANDOM_SEED,
            **comparison,
        }
    )
    return metrics


def _time_holdout_metrics(
    feat: pd.DataFrame,
    X: pd.DataFrame,
    y: pd.Series,
    estimator: Pipeline,
    month: str,
) -> dict[str, float | int | str]:
    """Evaluate on the configured future month when both splits are usable."""
    dates = pd.to_datetime(feat["order_datetime"], errors="coerce").dt.strftime("%Y-%m")
    train_mask, test_mask = dates < month, dates == month
    can_score = (
        train_mask.sum() > 30 and test_mask.sum() > 10 and y[test_mask].nunique() == 2
    )
    if not can_score:
        return {}
    temporal_model = CalibratedClassifierCV(
        estimator=estimator, method="sigmoid", cv=FOLDS
    ).fit(X.loc[train_mask], y.loc[train_mask])
    prediction = temporal_model.predict_proba(X.loc[test_mask])[:, 1]
    result = _probability_metrics(y[test_mask], prediction, "time_")
    result.update({"time_test_month": month, "time_test_n": int(test_mask.sum())})
    return result


def _write_training_artifacts(
    root: Path,
    feat: pd.DataFrame,
    X: pd.DataFrame,
    y: pd.Series,
    oof: np.ndarray,
    metrics: dict[str, Any],
    estimator: Pipeline,
    folds: StratifiedKFold,
) -> None:
    """Write metrics, predictions, calibration, ablation, and pincode reports."""
    (root / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    predictions = pd.DataFrame(
        {
            "order_id": feat["order_id"],
            "order_datetime": feat["order_datetime"],
            "risk": np.clip(oof, 0.01, 0.99),
            "actual": y,
        }
    )
    predictions.to_csv(root / "oof_predictions.csv", index=False)
    fraction, mean = calibration_curve(y, oof, n_bins=10, strategy="quantile")
    calibration = pd.DataFrame({"mean_predicted": mean, "fraction_positive": fraction})
    calibration.to_csv(root / "calibration.csv", index=False)
    _ablation(estimator, X, y, folds, metrics["cv_auc"], metrics["cv_log_loss"]).to_csv(
        root / "ablation.csv", index=False
    )
    _save_pincode_stats(feat, y, root)


def train_model(df: pd.DataFrame, output_dir: str | Path = "models") -> dict[str, Any]:
    """Fit selected calibrated model and write metrics, OOF risks and diagnostics."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    values = pd.to_numeric(df["order_value"], errors="coerce")
    value_edges = np.quantile(values.dropna(), [0.2, 0.4, 0.6, 0.8]).tolist()
    feat = build_features(df, value_edges=value_edges)
    y = (feat["final_status"] == "RTO").astype(int)
    X = feat[model_columns()]
    folds = StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=RANDOM_SEED)
    selected, comparison = _select_model(X, y, folds)
    oof = _calibrated_oof(selected, X, y, folds)
    metrics = _base_training_metrics(y, oof, comparison)
    metrics.update(
        _time_holdout_metrics(feat, X, y, selected, cfg["model"]["test_month"])
    )
    calibrated = CalibratedClassifierCV(
        estimator=selected, method="sigmoid", cv=FOLDS
    ).fit(X, y)
    joblib.dump(
        {"model": calibrated, "columns": model_columns(), "value_edges": value_edges},
        root / "model.joblib",
    )
    _write_training_artifacts(root, feat, X, y, oof, metrics, selected, folds)
    return metrics


def load_model(path: str | Path = "models/model.joblib") -> dict[str, Any]:
    """Load saved model or explain how to create it."""
    model_path = Path(path)
    if not model_path.exists():
        raise FileNotFoundError("Model is missing. Run python -m scripts.train first.")
    return joblib.load(model_path)


def predict_risk(df: pd.DataFrame, bundle: dict[str, Any] | None = None) -> np.ndarray:
    """Score orders and clip returned probabilities to safe bounds."""
    fitted = bundle or load_model()
    feat = build_features(df, use_llm=True, value_edges=fitted.get("value_edges"))
    return np.clip(
        fitted["model"].predict_proba(feat[fitted["columns"]])[:, 1], 0.01, 0.99
    )
