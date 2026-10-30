"""Run the complete local pipeline without an API key."""
from pathlib import Path
import pandas as pd
from engine.cleaning import clean_orders,training_rows
from engine.config import load_config
from engine.features import build_features
from engine.model import train_model,load_model
from engine.decision import decide
from engine.reasons import build_reason
from engine.store import connect
from scripts.explore import main as explore
from scripts.backtest import main as backtest
from scripts.memo_numbers import main as memo

def main() -> None:
    """Clean, train, analyze, score into SQLite, and generate reports."""
    cfg=load_config(); raw=pd.read_csv("orders_sample.csv"); cleaned=clean_orders(raw); explore(); train_model(training_rows(cleaned)); backtest(); bundle=load_model(); feat=build_features(cleaned,value_edges=bundle.get("value_edges")); risks=bundle["model"].predict_proba(feat[bundle["columns"]])[:,1]
    db=connect()
    for (_,row),risk in zip(feat.iterrows(),risks):
        record=row.to_dict(); dec=decide(record,float(risk),cfg,{"address_score":record["address_score"],"name_fake":record["name_fake"]}); dec=dec.__class__(**{**dec.__dict__,"reason":build_reason(dec,record)})
        db.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET action=excluded.action,risk=excluded.risk,reason=excluded.reason,discount_inr=excluded.discount_inr,est_saved=excluded.est_saved,est_lost=excluded.est_lost,est_discount_cost=excluded.est_discount_cost,est_msg_cost=excluded.est_msg_cost,order_date=excluded.order_date,is_first_time=excluded.is_first_time,order_value=excluded.order_value,state=excluded.state,city=excluded.city,llm_source=excluded.llm_source,decided_at=excluded.decided_at",(dec.order_id,dec.action,dec.risk,dec.reason,dec.discount_inr,dec.est_saved,dec.est_lost,dec.est_discount_cost,dec.est_msg_cost,str(record.get("order_datetime","")),int(record.get("is_first_time",0)),float(record.get("order_value",0)),record.get("state",""),record.get("city",""),record.get("llm_source","rules"),dec.decided_at))
    db.commit(); db.close(); memo(); print(f"Pipeline complete: {len(cleaned)} orders scored; reports written to docs/.")

if __name__=="__main__": main()
