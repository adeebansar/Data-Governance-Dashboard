"""AI governance: data-risk assessment for datasets that feed AI / ML systems.

Complements the data-quality engine with the checks AI governance frameworks
care about: personal-data exposure, representation / bias risk, and AI-readiness
gaps. Findings are mapped to the NIST AI Risk Management Framework and the EU AI
Act so the output reads like a governance review, not just a data scan.

Pure functions over a pandas DataFrame; the input frame is never mutated.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,63}$")

# Column-name hints for common categories of personal / sensitive data.
PII_HINTS = {
    "Email": ("email", "e-mail", "mail"),
    "Phone": ("phone", "mobile", "contact", "tel"),
    "Name": ("name", "surname", "first_name", "last_name", "full_name"),
    "Address": ("address", "street", "city", "zip", "postal", "postcode"),
    "Date of birth": ("dob", "birth", "birthday"),
    "Government ID": ("ssn", "national_id", "passport", "license", "aadhaar", "tax_id"),
    "Online identifier": ("ip_address", " ip", "device_id", "mac_address"),
}

# Short, accurate framework references shown beside each finding type.
FRAMEWORK = {
    "pii": "EU AI Act & GDPR: minimise and protect personal data; document a lawful basis.",
    "representation": "NIST AI RMF (Measure): test for harmful bias. EU AI Act: high-risk systems require representative, relevant data.",
    "readiness": "NIST AI RMF (Map): document data-quality limitations before a model relies on the data.",
}


def _name_has(col: str, hints: tuple[str, ...]) -> bool:
    low = " " + col.lower().replace("-", "_") + " "
    return any(h.strip() in low for h in hints)


def _non_blank(series: pd.Series) -> pd.Series:
    s = series.astype(str)
    return s[s.str.strip().ne("") & series.notna()]


def scan_pii(df: pd.DataFrame) -> list[dict]:
    """Flag columns that likely hold personal data, by name or by content."""
    findings = []
    for col in df.columns:
        cats = [cat for cat, hints in PII_HINTS.items() if _name_has(col, hints)]
        if not cats:
            present = _non_blank(df[col])
            if len(present) and present.str.match(EMAIL_RE).mean() > 0.5:
                cats = ["Email"]
        if cats:
            findings.append({"column": col, "categories": cats})
    return findings


def representation_report(df: pd.DataFrame, columns: list[str],
                          dominant: float = 0.8, rare: float = 0.05) -> list[dict]:
    """For each chosen sensitive attribute, summarise the group distribution and
    flag imbalance that could drive biased model behaviour."""
    reports = []
    for col in columns:
        if col not in df.columns:
            continue
        s = _non_blank(df[col])
        n = len(s)
        if not n:
            continue
        counts = s.value_counts()
        top = counts.iloc[0] / n
        smallest = counts.iloc[-1] / n
        flags = []
        if top >= dominant:
            flags.append(f"one group dominates ({round(top * 100)}%)")
        if smallest <= rare:
            flags.append(f"group(s) under-represented (below {round(rare * 100)}%)")
        reports.append({
            "column": col,
            "groups": int(len(counts)),
            "distribution": [
                {"value": str(k), "count": int(v), "pct": round(100 * v / n, 1)}
                for k, v in counts.head(8).items()
            ],
            "flags": flags,
        })
    return reports


def readiness_flags(df: pd.DataFrame, null_threshold: float = 0.2) -> list[dict]:
    """Columns whose missingness is high enough to need handling before training."""
    flags = []
    n = len(df)
    if not n:
        return flags
    for col in df.columns:
        blanks = int((df[col].isna() | df[col].astype(str).str.strip().eq("")).sum())
        pct = blanks / n
        if pct > null_threshold:
            flags.append({"column": col, "null_pct": round(100 * pct, 1)})
    return flags


def assess_ai_risk(df: pd.DataFrame, sensitive_columns: list[str] | None = None) -> dict[str, Any]:
    """Run all AI data-risk checks and roll them into a single risk level."""
    if df is None or df.empty:
        raise ValueError("No data to assess: the dataset is empty.")
    sensitive_columns = sensitive_columns or []
    pii = scan_pii(df)
    representation = representation_report(df, sensitive_columns)
    readiness = readiness_flags(df)
    rep_flagged = any(r["flags"] for r in representation)

    if pii and (rep_flagged or readiness):
        level = "High"
    elif pii or rep_flagged or readiness:
        level = "Medium"
    else:
        level = "Low"

    return {
        "risk_level": level,
        "pii": pii,
        "representation": representation,
        "readiness": readiness,
        "framework": FRAMEWORK,
    }
