"""Shared order input cleaning for training and serving."""
import logging
import re
import pandas as pd

LOGGER = logging.getLogger(__name__)

def clean_orders(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize order fields and retain flags needed for safe scoring."""
    out = df.copy()
    required=["order_id","order_datetime","customer_name","phone","address","city","state","pincode","order_value","num_items","items","customer_prior_orders","customer_prior_rto","utm_source"]
    absent=[name for name in required if name not in out.columns]
    out["missing_fields"]=[", ".join(absent)]*len(out)
    defaults={"order_id":"","order_datetime":pd.NaT,"customer_name":"","phone":"","address":"","city":"Unknown","state":"Unknown","pincode":"","order_value":0,"num_items":0,"items":"","customer_prior_orders":0,"customer_prior_rto":0,"utm_source":"Unknown","final_status":""}
    for column,value in defaults.items():
        if column not in out: out[column]=value
    fixes: dict[str, int] = {}
    string_columns = [col for col in out.columns if pd.api.types.is_object_dtype(out[col].dtype) or pd.api.types.is_string_dtype(out[col].dtype)]
    for col in string_columns:
        before = out[col].copy()
        out[col] = out[col].map(lambda x: x.strip() if isinstance(x, str) else x)
        fixes[f"trimmed_{col}"] = int((before != out[col]).sum())
    if "final_status" in out:
        out["final_status"] = out["final_status"].astype("string").str.strip().str.upper()
        fixes["in_transit"] = int((out["final_status"] == "IN_TRANSIT").sum())
        out["is_labeled"] = out["final_status"].isin(["DELIVERED", "RTO"])
    if "order_id" in out:
        fixes["exact_duplicates"] = int(out.duplicated().sum())
        out = out.drop_duplicates()
        if "order_datetime" in out:
            out["order_datetime"] = pd.to_datetime(out["order_datetime"], errors="coerce")
            out = out.sort_values("order_datetime").drop_duplicates("order_id", keep="last")
    if "order_value" in out:
        out["order_value"] = pd.to_numeric(out["order_value"], errors="coerce")
        out["valid_order_value"] = out["order_value"].gt(0).astype(int)
        fixes["invalid_order_value"] = int((out["valid_order_value"] == 0).sum())
    if "phone" in out:
        def normalize_phone(value: object) -> str:
            digits = re.sub(r"\D", "", str(value)) if pd.notna(value) else ""
            if len(digits) > 10 and digits.startswith("91"):
                digits = digits[2:]
            elif len(digits) > 10 and digits.startswith("0"):
                digits = digits[1:]
            return digits[-10:]
        out["phone"] = out["phone"].map(normalize_phone)
        out["phone_valid"] = out["phone"].str.fullmatch(r"[6-9]\d{9}").fillna(False).astype(int)
        fixes["invalid_phone"] = int((out["phone_valid"] == 0).sum())
    if "pincode" in out:
        def normalize_pin(value: object) -> str:
            if pd.isna(value):
                return ""
            try:
                pin = str(int(float(value)))
            except (ValueError, TypeError):
                pin = re.sub(r"\D", "", str(value))
            return pin if len(pin) == 6 and not pin.startswith("0") else ""
        out["pincode"] = out["pincode"].map(normalize_pin)
        out["pincode_missing"] = out["pincode"].eq("").astype(int)
        out["pin3"] = out["pincode"].str[:3].replace("", "Unknown")
        fixes["missing_pincode"] = int((out["pincode_missing"] == 1).sum())
    if "city" in out:
        fixes["missing_city"] = int(out["city"].isna().sum()+out["city"].astype(str).str.strip().eq("").sum())
        out["city"] = out["city"].fillna("").astype(str).str.strip().str.title().replace("", "Unknown")
    if "state" in out:
        out["state"] = out["state"].fillna("").astype(str).str.strip().str.title().replace("", "Unknown")
    if "address" in out:
        out["address"] = out["address"].fillna("").astype(str)
    for col in ["customer_prior_orders", "customer_prior_rto"]:
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).clip(lower=0)
    if {"customer_prior_orders", "customer_prior_rto"} <= set(out.columns):
        out["prior_rto_clipped"] = out["customer_prior_rto"] > out["customer_prior_orders"]
        fixes["prior_rto_clipped"] = int(out["prior_rto_clipped"].sum())
        out["customer_prior_rto"] = out[["customer_prior_orders", "customer_prior_rto"]].min(axis=1)
    LOGGER.info("Cleaning counts: %s", fixes)
    out.attrs["cleaning_counts"] = fixes
    return out.reset_index(drop=True)

def training_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return labeled, positive-value rows for model fitting."""
    return df.loc[df.get("is_labeled", True) & df.get("valid_order_value", 1).eq(1)].copy()
