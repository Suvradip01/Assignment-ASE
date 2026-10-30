"""Feature preparation shared by model training and serving."""
import pandas as pd
import numpy as np
from engine.geo import add_geo_features
from engine.llm import check_text
from engine.config import load_config
from engine.text_rules import address_score as rule_address_score, is_fake_name

def build_features(df: pd.DataFrame, use_llm: bool = False, value_edges: list[float] | None = None) -> pd.DataFrame:
    """Build leakage-safe tabular features from cleaned orders."""
    out = df.copy()
    defaults={"state":"Unknown","city":"Unknown","pin3":"Unknown","pincode_missing":1,"pincode":"","customer_name":"","customer_prior_orders":0,"customer_prior_rto":0,"address":"","phone_valid":0,"order_value":0,"num_items":0,"utm_source":"Unknown","missing_fields":""}
    for column,value in defaults.items():
        if column not in out: out[column]=value
    out = add_geo_features(out)
    junk_threshold=load_config()["rules"]["junk_address_below_score"]
    out["is_first_time"] = (pd.to_numeric(out.get("customer_prior_orders", 0), errors="coerce").fillna(0) == 0).astype(int)
    out["prior_rto_rate"] = out["customer_prior_rto"] / out["customer_prior_orders"].replace(0, 1)
    rule_scores=[rule_address_score(str(value)) for value in out["address"].fillna("")]
    rule_fake=[is_fake_name(str(value)) for value in out["customer_name"].fillna("")]
    text_results=check_text(out.to_dict("records"),allow_api=use_llm)
    out["address_score"]=[item["address_score"] for item in text_results]
    out["address_junk_rule"] = (pd.Series(rule_scores,index=out.index) < junk_threshold).astype(int)
    out["name_fake"]=[int(bool(item["name_fake"]) or rule_fake[index]) for index,item in enumerate(text_results)]
    out["address_language"]=[item["address_language"] for item in text_results]
    out["llm_source"]=[item["llm_source"] for item in text_results]
    out["address_has_digit"] = out["address"].str.contains(r"\d", regex=True, na=False).astype(int)
    values=pd.to_numeric(out["order_value"],errors="coerce")
    edges=value_edges if value_edges is not None else np.quantile(values.dropna(),[.2,.4,.6,.8]).tolist() if values.notna().any() else []
    out["value_bin"] = pd.cut(values,[-np.inf,*edges,np.inf],labels=False,duplicates="drop").fillna(0).astype(str)
    return out

def model_columns() -> list[str]:
    """Return approved model input columns."""
    return ["state", "city", "pin3", "pincode_missing", "pin_state_mismatch", "is_first_time", "customer_prior_orders", "customer_prior_rto", "prior_rto_rate", "value_bin", "num_items", "utm_source", "address_score", "address_junk_rule", "name_fake", "phone_valid", "address_has_digit"]
