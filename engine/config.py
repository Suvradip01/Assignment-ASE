"""Load and validate editable business settings."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib
import yaml


@dataclass(frozen=True)
class Settings:
    """Validated immutable configuration."""

    data: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        """Return a settings section."""
        return self.data[key]


def load_config(path: str | Path = "config/settings.yaml") -> Settings:
    """Load YAML settings and provide actionable validation errors."""
    file_path = Path(path)
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    _validate_probabilities(data)
    _validate_risk_bands(data)
    _validate_costs(data)
    _validate_conversions(data)
    _validate_quiet_hours(data)
    _validate_nonnegative_settings(data)
    return Settings(data)


def _validate_probabilities(data: dict[str, Any]) -> None:
    """Ensure probability-like business settings are within [0, 1]."""
    probabilities = [
        ("costs", "damaged_share_of_returns"),
        ("costs", "gross_margin_pct"),
        ("costs", "payment_gateway_fee_pct"),
        ("costs", "cod_rto_rate"),
        ("costs", "prepaid_rto_rate"),
        ("assumptions", "confirm_catches_share_of_returns"),
        ("assumptions", "confirm_loses_share_of_genuine"),
        ("assumptions", "nudge_annoyed_cancel_share"),
        ("rules", "no_reply_cancel_if_risk_at_least"),
        ("rules", "max_hold_share_alert"),
        ("rules", "llm_fallback_share_alert"),
        ("rules", "unclear_reply_share_alert"),
        ("rules", "control_group_pct"),
        ("prepaid_offer", "share_of_saving_given_to_customer"),
        ("prepaid_offer", "company_keeps_at_least_share"),
    ]
    for section, key in probabilities:
        value = float(data[section][key])
        if not 0 <= value <= 1:
            raise ValueError(f"{section}.{key} must be between 0 and 1")


def _validate_risk_bands(data: dict[str, Any]) -> None:
    """Check risk-band ranges and ascending action boundaries."""
    for group, bands in data["risk_bands"].items():
        for key in ["ship_below", "nudge_from", "hold_at_or_above"]:
            if not 0 <= float(bands[key]) <= 1:
                raise ValueError(f"risk_bands.{group}.{key} must be between 0 and 1")
        a, b, c = bands["ship_below"], bands["nudge_from"], bands["hold_at_or_above"]
        if not a < b < c:
            raise ValueError(
                f"risk bands for {group} must satisfy ship_below < nudge_from < hold_at_or_above"
            )


def _validate_costs(data: dict[str, Any]) -> None:
    """Reject negative cost assumptions."""
    for key, value in data["costs"].items():
        if value < 0:
            raise ValueError(f"costs.{key} cannot be negative")


def _validate_conversions(data: dict[str, Any]) -> None:
    """Require an ascending prepaid conversion table with valid rates."""
    conversions = data["assumptions"]["prepaid_conversion_by_discount_pct"]
    keys = [float(k) for k in conversions]
    if keys != sorted(keys) or any(
        not 0 <= float(v) <= 1 for v in conversions.values()
    ):
        raise ValueError(
            "prepaid conversion table must have ascending discount keys and probabilities in [0, 1]"
        )


def _validate_quiet_hours(data: dict[str, Any]) -> None:
    """Require quiet-hour settings to use valid 24-hour HH:MM values."""
    for boundary in data["whatsapp"]["quiet_hours"].values():
        try:
            if (
                len(boundary) != 5
                or boundary[2] != ":"
                or not 0 <= int(boundary[:2]) < 24
                or not 0 <= int(boundary[3:]) < 60
            ):
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError("whatsapp quiet hours must use HH:MM") from None


def _validate_nonnegative_settings(data: dict[str, Any]) -> None:
    """Reject negative minimum order and discount settings."""
    for section, keys in {
        "rules": ["min_order_value"],
        "prepaid_offer": ["min_discount_inr", "max_discount_pct", "round_to_inr"],
    }.items():
        for key in keys:
            if float(data[section][key]) < 0:
                raise ValueError(f"{section}.{key} cannot be negative")
    if float(data["prepaid_offer"]["round_to_inr"]) == 0:
        raise ValueError("prepaid_offer.round_to_inr must be greater than zero")


def config_hash(path: str | Path = "config/settings.yaml") -> str:
    """Return a short stable hash of the active YAML bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]
