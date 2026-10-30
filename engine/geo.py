"""Pincode prefix to state consistency checks."""
import pandas as pd

PREFIXES = {"Delhi": {"11"}, "Maharashtra": {f"{n}" for n in range(40, 45)}, "Tamil Nadu": {f"{n}" for n in range(60, 65)}, "West Bengal": {f"{n}" for n in range(70, 75)}, "Karnataka": {f"{n}" for n in range(56, 60)}, "Telangana": {"50"}, "Rajasthan": {f"{n}" for n in range(30, 35)}, "Assam": {"78"}, "Madhya Pradesh": {f"{n}" for n in range(45, 49)}, "Uttar Pradesh": {f"{n}" for n in range(20, 29)}, "Bihar": {f"{n}" for n in range(80, 86)}}

def pin_state_mismatch(pincode: object, state: object) -> int:
    """Return one when a known state conflicts with the pincode prefix."""
    prefixes = PREFIXES.get(str(state).strip().title())
    pin = str(pincode).strip()
    return int(bool(prefixes and len(pin) == 6 and pin[:2] not in prefixes))

def add_geo_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add pincode/state mismatch flags."""
    out = df.copy()
    out["pin_state_mismatch"] = [pin_state_mismatch(p, s) for p, s in zip(out.get("pincode", ""), out.get("state", "Unknown"))]
    return out
