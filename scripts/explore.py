"""Generate reproducible data quality and descriptive findings."""

from pathlib import Path

import pandas as pd

from engine.cleaning import clean_orders
from engine.features import build_features


def _write_quality_report(cleaned: pd.DataFrame) -> None:
    """Write generated cleaning counts and retained-row totals."""
    quality = cleaned.attrs.get("cleaning_counts", {})
    bullets = "\n".join(f"- {key}: {value}" for key, value in quality.items())
    report = (
        "# Data quality\n\n"
        f"{bullets}\n\nRows retained after exact duplicate removal: {len(cleaned)}. "
        "Unlabeled rows are retained for scoring and excluded from training.\n"
    )
    Path("docs/data_quality.md").write_text(report, encoding="utf-8")


def _segment_frames(labeled: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """Build the configured descriptive segments from labeled orders."""
    rows = [("Overall", labeled)]
    labeled["value_bin"] = pd.qcut(labeled["order_value"], 5, duplicates="drop").astype(
        str
    )
    group_columns = [
        ("state", "state"),
        ("city", "city"),
        ("first_time", "is_first_time"),
        ("prior_rto", "customer_prior_rto"),
        ("utm_source", "utm_source"),
        ("value_bin", "value_bin"),
    ]
    for label, column in group_columns:
        for value, group in labeled.groupby(column):
            if label != "city" or len(group) >= 20:
                rows.append((f"{label}={value}", group))
    rows.extend(
        (f"utm_source={source}, first_time={first_time}", group)
        for (source, first_time), group in labeled.groupby(
            ["utm_source", "is_first_time"]
        )
    )
    rows.extend(
        [
            ("Junk address", labeled[labeled.address_junk_rule == 1]),
            ("Fake name", labeled[labeled.name_fake == 1]),
            ("Pin/state mismatch", labeled[labeled.pin_state_mismatch == 1]),
            ("Invalid phone", labeled[labeled.phone_valid == 0]),
        ]
    )
    return rows


def _findings_table(rows: list[tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    """Summarize order counts and RTO rates for each descriptive segment."""
    return pd.DataFrame(
        [
            {
                "segment": name,
                "n": len(group),
                "rto": int(group.rto.sum()),
                "rto_rate": float(group.rto.mean()) if len(group) else 0,
            }
            for name, group in rows
        ]
    )


def _write_findings(table: pd.DataFrame) -> None:
    """Write CSV, markdown table, and computed highlight figures."""
    table.to_csv("docs/findings.csv", index=False)
    lines = [
        "# Data findings",
        "",
        "| Segment | Orders | RTO | RTO rate |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| {row.segment} | {row.n} | {row.rto} | {row.rto_rate:.1%} |"
        for row in table.itertuples()
    )
    _append_highlights(lines, table)
    Path("docs/findings.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_highlights(lines: list[str], table: pd.DataFrame) -> None:
    """Append selected highlights using values from the generated findings table."""
    highlight_names = [
        "state=Bihar",
        "state=Uttar Pradesh",
        "state=Maharashtra",
        "Junk address",
        "Fake name",
        "Pin/state mismatch",
        "Invalid phone",
    ]
    lookup = table.set_index("segment")
    lines.extend(["", "## Computed highlights", ""])
    for label in highlight_names:
        if label not in lookup.index:
            continue
        item = lookup.loc[label]
        lines.append(
            f"- {label}: {int(item['rto'])}/{int(item['n'])} RTO "
            f"({item['rto_rate']:.1%})."
        )


def main() -> None:
    """Write data quality counts and RTO findings."""
    raw = pd.read_csv("orders_sample.csv")
    cleaned = clean_orders(raw)
    Path("docs").mkdir(exist_ok=True)
    _write_quality_report(cleaned)
    features = build_features(cleaned)
    labeled = features[features["final_status"].isin(["DELIVERED", "RTO"])].copy()
    labeled["rto"] = (labeled.final_status == "RTO").astype(int)
    table = _findings_table(_segment_frames(labeled))
    _write_findings(table)
    print(table.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
