"""Declarative data-quality rules.

Two ways to get a schema:
1. CUSTOMER_MASTER_SCHEMA — a hand-authored, governance-grade rule set for the
   bundled sample. This is what a data steward would actually define for a
   master-data table.
2. infer_schema() — a best-effort schema for ANY uploaded CSV, so the tool is
   useful beyond the demo. It is intentionally conservative: it only asserts
   rules it can reasonably infer from column names and content.
"""

from __future__ import annotations

import pandas as pd

# Reference "today" for the bundled demo so results are reproducible.
SAMPLE_AS_OF = "2026-06-26"

EQUAL_WEIGHTS = {
    "Completeness": 1.0,
    "Uniqueness": 1.0,
    "Validity": 1.0,
    "Accuracy": 1.0,
    "Conformity": 1.0,
    "Consistency": 1.0,
    "Integrity": 1.0,
    "Timeliness": 1.0,
}

CUSTOMER_MASTER_SCHEMA = {
    "as_of": SAMPLE_AS_OF,
    "required_columns": [
        "customer_id", "full_name", "email", "phone", "country", "age",
        "signup_date", "last_active_date", "annual_revenue", "status",
    ],
    "unique_columns": ["customer_id", "email"],
    "email_columns": ["email"],
    "phone_columns": ["phone"],
    "non_negative_columns": ["annual_revenue"],
    "date_columns": ["signup_date", "last_active_date"],
    "no_future_columns": ["signup_date", "last_active_date"],
    "range_columns": {"age": (18, 100)},                     # accuracy / reasonableness
    "reference_columns": [                                    # referential integrity
        {"column": "referred_by", "references": "customer_id"},
    ],
    "allowed_values": {
        "country": {"United States", "Canada", "United Kingdom", "India", "Germany"},
        "status": {"Active", "Inactive", "Churned"},
    },
    "ordered_dates": [("signup_date", "last_active_date")],
    "timeliness": {"column": "last_active_date", "max_age_days": 365},
    "weights": EQUAL_WEIGHTS,
}

# Heuristics for auto-inference on arbitrary uploads.
_ID_HINTS = ("id", "key", "code", "number")
_EMAIL_HINTS = ("email", "e-mail", "mail")
_PHONE_HINTS = ("phone", "mobile", "contact", "tel")
_DATE_HINTS = ("date", "_at", "timestamp", "dob", "created", "updated")
_AMOUNT_HINTS = ("amount", "revenue", "price", "cost", "salary", "value", "qty", "quantity", "age")


def _name_matches(col: str, hints: tuple[str, ...]) -> bool:
    low = col.lower()
    return any(h in low for h in hints)


def _looks_like_dates(series: pd.Series, threshold: float = 0.7) -> bool:
    non_blank = series[series.notna() & series.astype(str).str.strip().ne("")]
    if non_blank.empty:
        return False
    parsed = pd.to_datetime(non_blank, errors="coerce", format="mixed")
    return parsed.notna().mean() >= threshold


def infer_schema(df: pd.DataFrame, as_of: str | None = None) -> dict:
    """Conservative schema for an unknown CSV."""
    cols = list(df.columns)
    n = len(df)

    unique_columns = []
    for c in cols:
        if not _name_matches(c, _ID_HINTS) or not n:
            continue
        non_blank = df[c][df[c].notna() & df[c].astype(str).str.strip().ne("")]
        if len(non_blank) and non_blank.nunique() >= 0.9 * len(non_blank):
            unique_columns.append(c)  # mostly-unique id-like column
    email_columns = [c for c in cols if _name_matches(c, _EMAIL_HINTS)]
    phone_columns = [c for c in cols if _name_matches(c, _PHONE_HINTS)]
    non_negative_columns = [
        c for c in cols
        if _name_matches(c, _AMOUNT_HINTS)
        and pd.to_numeric(df[c], errors="coerce").notna().any()
    ]
    date_columns = [
        c for c in cols
        if _name_matches(c, _DATE_HINTS) or _looks_like_dates(df[c])
    ]

    return {
        "as_of": as_of or SAMPLE_AS_OF,
        "required_columns": cols,            # completeness on every column
        "unique_columns": unique_columns,
        "email_columns": email_columns,
        "phone_columns": phone_columns,
        "non_negative_columns": non_negative_columns,
        "date_columns": date_columns,
        "no_future_columns": date_columns,   # no date should be in the future by default
        "range_columns": {},                 # can't infer reasonable bounds safely
        "reference_columns": [],             # can't infer relationships safely
        "allowed_values": {},                # can't infer approved sets safely
        "ordered_dates": [],                 # can't infer cross-field rules safely
        "timeliness": None,
        "weights": EQUAL_WEIGHTS,
    }
