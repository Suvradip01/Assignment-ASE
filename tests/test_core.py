"""Fast local tests for cleaning, configuration, economics and policies."""
from pathlib import Path
import pandas as pd
import pytest
from engine.cleaning import clean_orders
from engine.config import load_config,config_hash
from engine.economics import rto_cost,discount
from engine.decision import decide
from engine.text_rules import address_score,is_fake_name
from engine.whatsapp.parser import parse_reply
from engine.metrics import dashboard_aggregates
from engine.llm import check_text

def test_clean_phone_pin_and_prior_rto() -> None:
    """Normalize phone, pincode, and inconsistent history."""
    row={"order_id":"a","order_datetime":"2026-01-01","phone":"+91 98765 43210","pincode":110001.0,"city":None,"address":None,"customer_prior_orders":1,"customer_prior_rto":2,"final_status":" delivered ","order_value":0}
    out=clean_orders(pd.DataFrame([row])).iloc[0]
    assert out.phone=="9876543210" and out.phone_valid==1 and out.pincode=="110001"
    assert out.customer_prior_rto==1 and out.city=="Unknown" and out.address==""
    assert out.final_status=="DELIVERED" and out.valid_order_value==0

def test_duplicate_and_label_rules() -> None:
    """Drop exact duplicates and preserve only the latest duplicate order id."""
    base={"order_id":"a","order_datetime":"2026-01-01","order_value":10,"final_status":"IN_TRANSIT"}
    df=pd.DataFrame([base,base,{**base,"order_datetime":"2026-01-02","order_value":20}])
    out=clean_orders(df)
    assert len(out)==1 and out.iloc[0].order_value==20 and not out.iloc[0].is_labeled

def test_config_and_economics() -> None:
    """Validate settings and preserve worked RTO/discount example."""
    cfg=load_config(); assert rto_cost(cfg)==pytest.approx(169.4)
    assert discount(.5,{"order_value":649,"customer_prior_orders":1},cfg)==pytest.approx(30)
    assert len(config_hash())==12

def test_decision_boundaries_and_overrides() -> None:
    """Apply risk bands and address safeguards."""
    cfg=load_config(); base={"order_id":"1","order_datetime":"2026-01-01","customer_name":"Asha Sharma","phone":"9876543210","address":"12 Main Road","city":"Delhi","state":"Delhi","pincode":"110001","order_value":649,"num_items":1,"items":"Shampoo","customer_prior_orders":1,"customer_prior_rto":0,"utm_source":"meta_ads","phone_valid":1}
    assert decide(base,.2,cfg).action=="CONFIRM"
    assert decide(base,.8,cfg).action=="HOLD"
    junk={**base,"address_score":.1}
    assert decide(junk,.1,cfg).flow=="confirm_address"
    assert decide({**base,"order_value":0},.1,cfg).flags==["invalid_order_value"]

def test_hold_reason_uses_clear_estimate_labels_and_currency() -> None:
    """Format HOLD impact estimates with rupees and distinguish both estimates."""
    cfg=load_config(); base={"order_id":"1","order_datetime":"2026-01-01","customer_name":"asdf","phone":"bad","address":"xyz","city":"Delhi","state":"Delhi","pincode":"110001","order_value":649,"num_items":1,"items":"Shampoo","customer_prior_orders":1,"customer_prior_rto":0,"utm_source":"meta_ads","phone_valid":0,"address_score":.1,"name_fake":True}
    decision=decide(base,.2,cfg)
    assert decision.action=="HOLD"
    assert "₹" in decision.reason and "?" not in decision.reason
    assert "Estimated return cost avoided" in decision.reason
    assert "estimated cost if a genuine order is held" in decision.reason

def test_text_parser_and_metrics() -> None:
    """Recognize common text and aggregate empty buckets safely."""
    assert address_score(".")<.3 and is_fake_name("asdf")
    assert parse_reply("haan 👍","AWAITING_CONFIRMATION").value=="YES"
    assert parse_reply("no problem, haan bhej do","AWAITING_CONFIRMATION").value=="UNCLEAR"
    result=dashboard_aggregates(pd.DataFrame([{"action":"SHIP","est_saved":0,"est_lost":0,"est_discount_cost":0,"est_msg_cost":0}]))
    assert result["counts"]["SHIP"]==1 and result["counts"]["HOLD"]==0

def test_llm_rules_fallback_and_privacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No-key text checks remain local and cache only text features."""
    monkeypatch.setenv("LLM_PROVIDER","none")
    cache=tmp_path/"cache.jsonl"; record={"order_id":"private-id","phone":"9999999999","order_value":9999,"customer_name":"asdf","address":"xyz","city":"Delhi","state":"Delhi"}
    result=check_text([record],cache_path=cache,allow_api=True)[0]
    assert result["llm_source"]=="rules" and result["name_fake"] is True
    assert not cache.exists() or "private-id" not in cache.read_text(encoding="utf-8")
