"""Generate numerical memo inputs from model outputs and data."""
from pathlib import Path
import json
from scripts.backtest import main as run_backtest
from scripts.discount_table import main as run_discounts

def main() -> None:
    """Run reproducible reports and write memo number links."""
    run_backtest(); run_discounts(); metrics=json.loads(Path("models/metrics.json").read_text(encoding="utf-8"))
    sections = [
        ("Data findings", Path("docs/findings.md")),
        ("Policy comparison and sensitivity", Path("docs/backtest_summary.md")),
        ("Discount calculations", Path("docs/discount_table.md")),
    ]
    content = ["# Memo numbers (generated)", "", "Model metrics:", "", "\n".join(f"- {key}: {value}" for key, value in metrics.items())]
    for title, path in sections:
        if path.exists():
            content.extend(["", f"## {title}", "", path.read_text(encoding="utf-8")])
    content.extend(["", "These generated figures are supporting analysis, not the founder memo."])
    Path("docs/memo_numbers.md").write_text("\n".join(content) + "\n", encoding="utf-8")

if __name__=="__main__": main()
