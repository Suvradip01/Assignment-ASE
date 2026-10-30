"""Dashboard and backtest aggregates."""
import pandas as pd

def dashboard_aggregates(df: pd.DataFrame) -> dict[str, object]:
    """Aggregate action counts and estimated impact for a selected day."""
    result={"counts":df["action"].value_counts().to_dict() if len(df) else {},"n":len(df)}
    for action in ["SHIP","CONFIRM","NUDGE","HOLD"]: result["counts"].setdefault(action,0)
    result["saved"]=float(df.get("est_saved",pd.Series(dtype=float)).sum()); result["lost"]=float(df.get("est_lost",pd.Series(dtype=float)).sum()); result["costs"]=float(df.get("est_discount_cost",pd.Series(dtype=float)).sum()+df.get("est_msg_cost",pd.Series(dtype=float)).sum()); result["net"]=result["saved"]-result["lost"]-result["costs"]
    return result
