"""Tests for the AI governance data-risk module against the sample dataset."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ai_risk
import data_quality as dq

SAMPLE = ROOT / "sample_data" / "customer_master_messy.csv"


@pytest.fixture(scope="module")
def df():
    return dq.load_csv(SAMPLE)


def test_pii_scan_flags_personal_columns(df):
    cols = {f["column"] for f in ai_risk.scan_pii(df)}
    assert {"full_name", "email", "phone"}.issubset(cols)
    assert "annual_revenue" not in cols  # not personal data


def test_content_based_email_detection():
    d = pd.DataFrame({"field_x": ["a@b.com", "x@y.org", "z@w.net"]})
    cols = {f["column"] for f in ai_risk.scan_pii(d)}
    assert "field_x" in cols  # caught by content even without a PII-style name


def test_representation_report(df):
    rep = {r["column"]: r for r in ai_risk.representation_report(df, ["country", "status"])}
    assert rep["country"]["groups"] >= 5
    assert sum(d["count"] for d in rep["country"]["distribution"]) > 0


def test_representation_flags_imbalance():
    d = pd.DataFrame({"grp": ["A"] * 95 + ["B"] * 5})
    rep = ai_risk.representation_report(d, ["grp"])
    assert rep[0]["flags"]  # 95% dominant + 5% rare should flag


def test_assess_risk_level(df):
    risk = ai_risk.assess_ai_risk(df, ["country", "status"])
    assert risk["risk_level"] in {"Low", "Medium", "High"}
    assert risk["pii"]  # personal data is present in the sample


def test_empty_dataframe_raises():
    with pytest.raises(ValueError):
        ai_risk.assess_ai_risk(pd.DataFrame())
