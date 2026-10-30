"""Generate reproducible data quality and descriptive findings."""
from pathlib import Path
import pandas as pd
from engine.cleaning import clean_orders
from engine.features import build_features

def main() -> None:
    """Write data quality counts and RTO findings."""
    raw=pd.read_csv("orders_sample.csv"); clean=clean_orders(raw); Path("docs").mkdir(exist_ok=True)
    quality=clean.attrs.get("cleaning_counts",{}); Path("docs/data_quality.md").write_text("# Data quality\n\n"+"\n".join(f"- {key}: {value}" for key,value in quality.items())+f"\n\nRows retained after exact duplicate removal: {len(clean)}. Unlabeled rows are retained for scoring and excluded from training.\n",encoding="utf-8")
    df=build_features(clean); labeled=df[df["final_status"].isin(["DELIVERED","RTO"])].copy(); labeled["rto"]=(labeled.final_status=="RTO").astype(int)
    rows=[("Overall",labeled)]
    labeled["value_bin"] = pd.qcut(labeled["order_value"],5,duplicates="drop").astype(str)
    rows += [(f"{name}={value}",sub) for name,col in [("state","state"),("city","city"),("first_time","is_first_time"),("prior_rto","customer_prior_rto"),("utm_source","utm_source"),("value_bin","value_bin")] for value,sub in labeled.groupby(col) if (name!="city" or len(sub)>=20)]
    rows += [(f"utm_source={source}, first_time={first}",sub) for (source,first),sub in labeled.groupby(["utm_source","is_first_time"])]
    rows += [("Junk address",labeled[labeled.address_junk_rule==1]),("Fake name",labeled[labeled.name_fake==1]),("Pin/state mismatch",labeled[labeled.pin_state_mismatch==1]),("Invalid phone",labeled[labeled.phone_valid==0])]
    table=pd.DataFrame([{"segment":name,"n":len(sub),"rto":int(sub.rto.sum()),"rto_rate":float(sub.rto.mean()) if len(sub) else 0} for name,sub in rows]); table.to_csv("docs/findings.csv",index=False)
    lines=["# Data findings", "", "| Segment | Orders | RTO | RTO rate |", "|---|---:|---:|---:|"]
    lines.extend(f"| {row.segment} | {row.n} | {row.rto} | {row.rto_rate:.1%} |" for row in table.itertuples())
    # Each highlight is computed from the grouped table, keeping figures reproducible.
    highlight_names=["state=Bihar","state=Uttar Pradesh","state=Maharashtra","Junk address","Fake name","Pin/state mismatch","Invalid phone"]
    lookup=table.set_index("segment")
    lines += ["", "## Computed highlights", ""]
    for label in highlight_names:
        if label in lookup.index:
            item=lookup.loc[label]; lines.append(f"- {label}: {int(item['rto'])}/{int(item['n'])} RTO ({item['rto_rate']:.1%}).")
    Path("docs/findings.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(table.head(15).to_string(index=False))

if __name__=="__main__": main()
