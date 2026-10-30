"""Shared order input cleaning for training and serving."""

import logging
import re

import pandas as pd

LOGGER = logging.getLogger(__name__)
REQUIRED_FIELDS = [
    "order_id",
    "order_datetime",
    "customer_name",
    "phone",
    "address",
    "city",
    "state",
    "pincode",
    "order_value",
    "num_items",
    "items",
    "customer_prior_orders",
    "customer_prior_rto",
    "utm_source",
]
DEFAULTS = {
    "order_id": "",
    "order_datetime": pd.NaT,
    "customer_name": "",
    "phone": "",
    "address": "",
    "city": "Unknown",
    "state": "Unknown",
    "pincode": "",
    "order_value": 0,
    "num_items": 0,
    "items": "",
    "customer_prior_orders": 0,
    "customer_prior_rto": 0,
    "utm_source": "Unknown",
    "final_status": "",
}


def _add_defaults(out: pd.DataFrame) -> pd.DataFrame:
    """Add absent columns with safe serving defaults."""
    for column, value in DEFAULTS.items():
        if column not in out:
            out[column] = value
    return out


def _trim_string_columns(out: pd.DataFrame, fixes: dict[str, int]) -> None:
    """Trim surrounding whitespace and count changed values."""
    string_columns = [
        column
        for column in out.columns
        if pd.api.types.is_object_dtype(out[column].dtype)
        or pd.api.types.is_string_dtype(out[column].dtype)
    ]
    for column in string_columns:
        before = out[column].copy()
        out[column] = out[column].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )
        fixes[f"trimmed_{column}"] = int((before != out[column]).sum())


def _clean_labels(out: pd.DataFrame, fixes: dict[str, int]) -> None:
    """Normalize delivery labels and mark rows that can train the model."""
    out["final_status"] = out["final_status"].astype("string").str.strip().str.upper()
    fixes["in_transit"] = int((out["final_status"] == "IN_TRANSIT").sum())
    out["is_labeled"] = out["final_status"].isin(["DELIVERED", "RTO"])


def _deduplicate_orders(out: pd.DataFrame, fixes: dict[str, int]) -> pd.DataFrame:
    """Drop exact duplicates and keep the latest row for each order ID."""
    fixes["exact_duplicates"] = int(out.duplicated().sum())
    out = out.drop_duplicates()
    out["order_datetime"] = pd.to_datetime(out["order_datetime"], errors="coerce")
    return out.sort_values("order_datetime").drop_duplicates("order_id", keep="last")


def _clean_order_values(out: pd.DataFrame, fixes: dict[str, int]) -> None:
    """Parse order values and flag non-positive or invalid amounts."""
    out["order_value"] = pd.to_numeric(out["order_value"], errors="coerce")
    out["valid_order_value"] = out["order_value"].gt(0).astype(int)
    fixes["invalid_order_value"] = int((out["valid_order_value"] == 0).sum())


def _normalize_phone(value: object) -> str:
    """Return a ten-digit Indian phone value when possible."""
    digits = re.sub(r"\D", "", str(value)) if pd.notna(value) else ""
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) > 10 and digits.startswith("0"):
        digits = digits[1:]
    return digits[-10:]


def _clean_phones(out: pd.DataFrame, fixes: dict[str, int]) -> None:
    """Normalize phone values and add a validity flag."""
    out["phone"] = out["phone"].map(_normalize_phone)
    out["phone_valid"] = (
        out["phone"].str.fullmatch(r"[6-9]\d{9}").fillna(False).astype(int)
    )
    fixes["invalid_phone"] = int((out["phone_valid"] == 0).sum())


def _normalize_pincode(value: object) -> str:
    """Return a valid six-digit pincode or an empty value."""
    if pd.isna(value):
        return ""
    try:
        pincode = str(int(float(value)))
    except (ValueError, TypeError):
        pincode = re.sub(r"\D", "", str(value))
    return pincode if len(pincode) == 6 and not pincode.startswith("0") else ""


def _clean_pincodes(out: pd.DataFrame, fixes: dict[str, int]) -> None:
    """Normalize pincodes and add missing and prefix features."""
    out["pincode"] = out["pincode"].map(_normalize_pincode)
    out["pincode_missing"] = out["pincode"].eq("").astype(int)
    out["pin3"] = out["pincode"].str[:3].replace("", "Unknown")
    fixes["missing_pincode"] = int((out["pincode_missing"] == 1).sum())


def _clean_location_text(out: pd.DataFrame, fixes: dict[str, int]) -> None:
    """Normalize city, state, and address text."""
    fixes["missing_city"] = int(
        out["city"].isna().sum() + out["city"].astype(str).str.strip().eq("").sum()
    )
    for column in ["city", "state"]:
        out[column] = (
            out[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.title()
            .replace("", "Unknown")
        )
    out["address"] = out["address"].fillna("").astype(str)


def _clean_customer_history(out: pd.DataFrame, fixes: dict[str, int]) -> None:
    """Clamp customer history values and repair impossible prior RTO counts."""
    for column in ["customer_prior_orders", "customer_prior_rto"]:
        out[column] = (
            pd.to_numeric(out[column], errors="coerce").fillna(0).clip(lower=0)
        )
    out["prior_rto_clipped"] = out["customer_prior_rto"] > out["customer_prior_orders"]
    fixes["prior_rto_clipped"] = int(out["prior_rto_clipped"].sum())
    out["customer_prior_rto"] = out[
        ["customer_prior_orders", "customer_prior_rto"]
    ].min(axis=1)


def clean_orders(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize order fields and retain flags needed for safe scoring."""
    out = df.copy()
    absent = [name for name in REQUIRED_FIELDS if name not in out.columns]
    out["missing_fields"] = [", ".join(absent)] * len(out)
    out = _add_defaults(out)
    fixes: dict[str, int] = {}
    _trim_string_columns(out, fixes)
    _clean_labels(out, fixes)
    out = _deduplicate_orders(out, fixes)
    _clean_order_values(out, fixes)
    _clean_phones(out, fixes)
    _clean_pincodes(out, fixes)
    _clean_location_text(out, fixes)
    _clean_customer_history(out, fixes)
    LOGGER.info("Cleaning counts: %s", fixes)
    out.attrs["cleaning_counts"] = fixes
    return out.reset_index(drop=True)


def training_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return labeled, positive-value rows for model fitting."""
    return df.loc[
        df.get("is_labeled", True) & df.get("valid_order_value", 1).eq(1)
    ].copy()
