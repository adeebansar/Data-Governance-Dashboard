"""Unit tests for the data-quality engine.

Strategy: the sample dataset plants a known, documented set of issues at known
row indices. These tests assert the engine catches each planted issue. Because
the ground truth is fixed, the assertions are exact, not fuzzy.

Run:  python -m pytest -q      (or)      python tests/test_data_quality.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import data_quality as dq
from rules_config import CUSTOMER_MASTER_SCHEMA, infer_schema

SAMPLE = ROOT / "sample_data" / "customer_master_messy.csv"


@pytest.fixture(scope="module")
def report() -> dict:
    df = dq.load_csv(SAMPLE)
    return dq.run_quality_report(df, CUSTOMER_MASTER_SCHEMA)


def _check(report: dict, dimension: str, name_contains: str) -> dict:
    for c in report["dimensions"][dimension]["checks"]:
        if name_contains in c["name"]:
            return c
    raise AssertionError(f"check '{name_contains}' not found in {dimension}")


# --- shape ---------------------------------------------------------------- #
def test_report_shape(report):
    assert report["row_count"] == 45
    assert report["column_count"] == 11
    assert 0 < report["overall_score"] < 100  # issues exist, but not everything fails
    assert set(report["dimensions"]) == {
        "Completeness", "Uniqueness", "Validity", "Accuracy",
        "Conformity", "Consistency", "Integrity", "Timeliness",
    }


# --- discrepancy categories ---------------------------------------------- #
def test_categories_present_and_tagged(report):
    cats = {c["category"] for c in report["categories"]}
    assert {"Missing data", "Duplicate data", "Invalid data", "Implausible data",
            "Non-conforming data", "Inconsistent data", "Orphaned data", "Stale data"} == cats
    # every check carries its plain-language category
    for d in report["dimensions"].values():
        for c in d["checks"]:
            assert c["category"]
    # the 'Missing data' category should report affected rows (28, 29, 30)
    missing = next(c for c in report["categories"] if c["category"] == "Missing data")
    assert missing["affected_rows"] == 3


# --- completeness --------------------------------------------------------- #
def test_completeness_catches_missing_values(report):
    assert 28 in _check(report, "Completeness", "email is populated")["failing_rows"]
    assert 29 in _check(report, "Completeness", "full_name is populated")["failing_rows"]
    assert 30 in _check(report, "Completeness", "annual_revenue is populated")["failing_rows"]
    # a fully-populated column should pass cleanly
    assert _check(report, "Completeness", "customer_id is populated")["failed"] == 0


# --- uniqueness ----------------------------------------------------------- #
def test_uniqueness_flags_both_duplicate_rows(report):
    id_check = _check(report, "Uniqueness", "customer_id is unique")
    assert {0, 31}.issubset(set(id_check["failing_rows"]))  # original + duplicate
    email_check = _check(report, "Uniqueness", "email is unique")
    assert {4, 32}.issubset(set(email_check["failing_rows"]))


# --- validity ------------------------------------------------------------- #
def test_validity_email_phone_revenue_dates(report):
    assert 33 in _check(report, "Validity", "email is a valid email")["failing_rows"]
    assert 34 in _check(report, "Validity", "phone is a valid phone")["failing_rows"]
    assert 35 in _check(report, "Validity", "annual_revenue is a non-negative")["failing_rows"]
    assert 36 in _check(report, "Validity", "signup_date is a parseable date")["failing_rows"]
    assert 40 in _check(report, "Validity", "signup_date is not in the future")["failing_rows"]


# --- accuracy (reasonableness) ------------------------------------------- #
def test_accuracy_flags_implausible_age(report):
    chk = _check(report, "Accuracy", "age is within")
    assert 43 in chk["failing_rows"]  # age 250 (too high)
    assert 44 in chk["failing_rows"]  # age 7  (too low)


# --- integrity (referential) --------------------------------------------- #
def test_integrity_flags_orphaned_reference(report):
    chk = _check(report, "Integrity", "referred_by references an existing")
    assert 42 in chk["failing_rows"]  # references C9999, which does not exist


# --- conformity ----------------------------------------------------------- #
def test_conformity_allowed_values(report):
    assert 37 in _check(report, "Conformity", "country uses an allowed value")["failing_rows"]
    assert 38 in _check(report, "Conformity", "status uses an allowed value")["failing_rows"]


# --- consistency ---------------------------------------------------------- #
def test_consistency_date_order(report):
    chk = _check(report, "Consistency", "last_active_date is on/after signup_date")
    assert 39 in chk["failing_rows"]


# --- timeliness ----------------------------------------------------------- #
def test_timeliness_flags_stale_record(report):
    chk = _check(report, "Timeliness", "last_active_date is fresh")
    assert 41 in chk["failing_rows"]


# --- profiling ------------------------------------------------------------ #
def test_profile_has_all_columns(report):
    cols = {p["column"] for p in report["profile"]}
    assert set(CUSTOMER_MASTER_SCHEMA["required_columns"]).issubset(cols)
    assert {"age", "referred_by"}.issubset(cols)
    assert len(cols) == 11
    email = next(p for p in report["profile"] if p["column"] == "email")
    assert email["nulls"] == 1  # one blank email row


# --- inference + guards --------------------------------------------------- #
def test_infer_schema_classifies_columns():
    df = pd.DataFrame({
        "user_id": ["1", "2", "3"],
        "email": ["a@b.com", "x@y.com", "bad"],
        "signup_date": ["2024-01-01", "2024-02-01", "2024-03-01"],
        "salary": ["100", "200", "300"],
    })
    schema = infer_schema(df)
    assert "user_id" in schema["unique_columns"]
    assert "email" in schema["email_columns"]
    assert "signup_date" in schema["date_columns"]
    assert "salary" in schema["non_negative_columns"]


def test_empty_dataframe_raises():
    with pytest.raises(ValueError):
        dq.run_quality_report(pd.DataFrame(), infer_schema(pd.DataFrame()))


# --- regression tests for issues caught in the pre-publish review --------- #
def test_load_csv_preserves_blank_lines():
    import io
    df = dq.load_csv(io.StringIO("a,b\n1,2\n\n3,4\n"))
    assert len(df) == 3  # the stray blank line is kept, not silently dropped


def test_email_check_rejects_injection_payload():
    df = pd.DataFrame({"email": ["good@example.com", "bad@example.com<script>"]})
    report = dq.run_quality_report(
        df, {"required_columns": ["email"], "email_columns": ["email"]}
    )
    chk = next(c for c in report["dimensions"]["Validity"]["checks"]
               if "email is a valid email" in c["name"])
    assert 1 in chk["failing_rows"]      # the <script> payload is rejected
    assert 0 not in chk["failing_rows"]  # a normal address still passes


def test_timezone_aware_dates_do_not_crash():
    df = pd.DataFrame({"event_at": ["2023-01-01T00:00:00Z", "2023-06-01T00:00:00+05:00"]})
    report = dq.run_quality_report(df, {
        "required_columns": ["event_at"],
        "date_columns": ["event_at"],
        "no_future_columns": ["event_at"],
        "as_of": "2026-06-26",
    })
    assert report["row_count"] == 2  # mixed-offset timestamps handled, no crash


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
