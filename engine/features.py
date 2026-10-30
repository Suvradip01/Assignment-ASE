"""Feature preparation shared by model training and serving."""

import numpy as np
import pandas as pd

from engine.config import load_config
from engine.geo import add_geo_features
from engine.llm import check_text
from engine.text_rules import address_score as rule_address_score
from engine.text_rules import is_fake_name

FEATURE_DEFAULTS = {
    "state": "Unknown",
    "city": "Unknown",
    "pin3": "Unknown",
    "pincode_missing": 1,
    "pincode": "",
    "customer_name": "",
    "customer_prior_orders": 0,
    "customer_prior_rto": 0,
    "address": "",
    "phone_valid": 0,
    "order_value": 0,
    "num_items": 0,
    "utm_source": "Unknown",
    "missing_fields": "",
}


def _add_defaults(frame: pd.DataFrame) -> pd.DataFrame:
    """Add safe defaults for optional feature inputs."""
    for column, value in FEATURE_DEFAULTS.items():
        if column not in frame:
            frame[column] = value
    return frame


def _add_text_features(frame: pd.DataFrame, use_llm: bool) -> pd.DataFrame:
    """Add cached, provider, and local-rule text features."""
    threshold = load_config()["rules"]["junk_address_below_score"]
    addresses = frame["address"].fillna("").astype(str)
    names = frame["customer_name"].fillna("").astype(str)
    rule_scores = [rule_address_score(value) for value in addresses]
    rule_fake = [is_fake_name(value) for value in names]
    results = check_text(frame.to_dict("records"), allow_api=use_llm)
    frame["address_score"] = [item["address_score"] for item in results]
    frame["address_junk_rule"] = (
        pd.Series(rule_scores, index=frame.index) < threshold
    ).astype(int)
    frame["name_fake"] = [
        int(bool(item["name_fake"]) or rule_fake[index])
        for index, item in enumerate(results)
    ]
    frame["address_language"] = [item["address_language"] for item in results]
    frame["llm_source"] = [item["llm_source"] for item in results]
    frame["address_has_digit"] = addresses.str.contains(
        r"\d", regex=True, na=False
    ).astype(int)
    return frame


def _value_bin_edges(values: pd.Series, edges: list[float] | None) -> list[float]:
    """Use supplied training edges or calculate quantiles for a new dataset."""
    if edges is not None:
        return edges
    available = values.dropna()
    if available.empty:
        return []
    return np.quantile(available, [0.2, 0.4, 0.6, 0.8]).tolist()


def _add_value_bins(frame: pd.DataFrame, edges: list[float] | None) -> None:
    """Add a categorical order-value band using fixed or local quantiles."""
    values = pd.to_numeric(frame["order_value"], errors="coerce")
    boundaries = _value_bin_edges(values, edges)
    frame["value_bin"] = (
        pd.cut(values, [-np.inf, *boundaries, np.inf], labels=False, duplicates="drop")
        .fillna(0)
        .astype(str)
    )


def build_features(
    df: pd.DataFrame, use_llm: bool = False, value_edges: list[float] | None = None
) -> pd.DataFrame:
    """Build leakage-safe tabular features from cleaned orders."""
    frame = _add_defaults(df.copy())
    frame = add_geo_features(frame)
    frame["is_first_time"] = (
        pd.to_numeric(frame["customer_prior_orders"], errors="coerce").fillna(0) == 0
    ).astype(int)
    frame["prior_rto_rate"] = frame["customer_prior_rto"] / frame[
        "customer_prior_orders"
    ].replace(0, 1)
    frame = _add_text_features(frame, use_llm)
    _add_value_bins(frame, value_edges)
    return frame


def model_columns() -> list[str]:
    """Return approved model input columns."""
    return [
        "state",
        "city",
        "pin3",
        "pincode_missing",
        "pin_state_mismatch",
        "is_first_time",
        "customer_prior_orders",
        "customer_prior_rto",
        "prior_rto_rate",
        "value_bin",
        "num_items",
        "utm_source",
        "address_score",
        "address_junk_rule",
        "name_fake",
        "phone_valid",
        "address_has_digit",
    ]
