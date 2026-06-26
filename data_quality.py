"""Data-quality rule engine.

Pure functions over a pandas DataFrame. Each dimension check returns a plain
dict (the input frame is never mutated), so results are easy to test, serialise,
and render. The eight dimensions follow the standard data-management quality
framework: Completeness, Uniqueness, Validity, Accuracy, Conformity,
Consistency, Integrity, Timeliness.

No external services are called: assessment runs locally and no uploaded data
leaves the process.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any, Union

import pandas as pd

# TLD restricted to letters (2-63) so payloads like "a@b.com<script>" are rejected.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,63}$")
MIN_PHONE_DIGITS = 10

# Plain-language discrepancy category for each formal quality dimension.
DIMENSION_CATEGORY = {
    "Completeness": "Missing data",
    "Uniqueness": "Duplicate data",
    "Validity": "Invalid data",
    "Accuracy": "Implausible data",
    "Conformity": "Non-conforming data",
    "Consistency": "Inconsistent data",
    "Integrity": "Orphaned data",
    "Timeliness": "Stale data",
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _is_blank(series: pd.Series) -> pd.Series:
    """True where a value is null or an empty/whitespace string."""
    return series.isna() | series.astype(str).str.strip().eq("")


def _make_check(name: str, dimension: str, failed_mask: pd.Series, detail: str) -> dict[str, Any]:
    """Build a check result from a boolean mask of FAILING rows."""
    total = int(len(failed_mask))
    failed = int(failed_mask.sum())
    passed = total - failed
    pass_rate = round(passed / total, 4) if total else 1.0
    failing_rows = failed_mask[failed_mask].index.tolist()
    return {
        "name": name,
        "dimension": dimension,
        "total": total,
        "failed": failed,
        "passed": passed,
        "pass_rate": pass_rate,
        "failing_rows": [int(i) for i in failing_rows],
        "detail": detail,
    }


def _parse_dates(series: pd.Series) -> pd.Series:
    """Parse to UTC datetime; unparseable -> NaT. utc=True keeps comparisons
    safe even when the input mixes naive and timezone-aware timestamps."""
    return pd.to_datetime(series, errors="coerce", format="mixed", utc=True)


def _as_of_datetime(as_of: str | None) -> datetime:
    """Reference 'today' as a timezone-aware (UTC) datetime, to compare cleanly
    against the UTC-normalised parsed dates."""
    base = datetime.strptime(as_of, "%Y-%m-%d") if as_of else datetime.now()
    return base.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Dimension checks
# --------------------------------------------------------------------------- #
def check_completeness(df: pd.DataFrame, required_columns: list[str]) -> list[dict]:
    checks = []
    for col in required_columns:
        if col not in df.columns:
            continue
        mask = _is_blank(df[col])
        checks.append(_make_check(f"{col} is populated", "Completeness", mask,
                                  "Value is missing or empty."))
    return checks


def check_uniqueness(df: pd.DataFrame, unique_columns: list[str]) -> list[dict]:
    checks = []
    for col in unique_columns:
        if col not in df.columns:
            continue
        non_blank = ~_is_blank(df[col])
        dup = df[col].duplicated(keep=False) & non_blank
        checks.append(_make_check(f"{col} is unique", "Uniqueness", dup,
                                  "Duplicate value found in a column that must be unique."))
    # Full-row duplicate detection is schema-independent and always meaningful,
    # so it runs for any dataset (configured unique columns or not).
    full_dup = df.duplicated(keep=False)
    checks.append(_make_check("No duplicate records", "Uniqueness", full_dup,
                              "Entire row is duplicated."))
    return checks


def _check_emails(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    checks = []
    for col in columns:
        if col not in df.columns:
            continue
        present = ~_is_blank(df[col])
        bad = present & ~df[col].astype(str).str.match(EMAIL_RE)
        checks.append(_make_check(f"{col} is a valid email", "Validity", bad,
                                  "Email does not match a valid pattern."))
    return checks


def _check_phones(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    checks = []
    for col in columns:
        if col not in df.columns:
            continue
        present = ~_is_blank(df[col])
        digit_count = df[col].astype(str).str.replace(r"\D", "", regex=True).str.len()
        bad = present & (digit_count < MIN_PHONE_DIGITS)
        checks.append(_make_check(f"{col} is a valid phone", "Validity", bad,
                                  f"Phone has fewer than {MIN_PHONE_DIGITS} digits."))
    return checks


def _check_non_negative(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    checks = []
    for col in columns:
        if col not in df.columns:
            continue
        present = ~_is_blank(df[col])
        numeric = pd.to_numeric(df[col], errors="coerce")
        bad = present & (numeric.isna() | (numeric < 0))
        checks.append(_make_check(f"{col} is a non-negative number", "Validity", bad,
                                  "Value is non-numeric or negative."))
    return checks


def _check_dates_parseable(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    checks = []
    for col in columns:
        if col not in df.columns:
            continue
        present = ~_is_blank(df[col])
        parsed = _parse_dates(df[col])
        bad = present & parsed.isna()
        checks.append(_make_check(f"{col} is a parseable date", "Validity", bad,
                                  "Value is not a recognisable date."))
    return checks


def _check_no_future(df: pd.DataFrame, columns: list[str], as_of: str | None) -> list[dict]:
    checks = []
    as_of_dt = _as_of_datetime(as_of)
    for col in columns:
        if col not in df.columns:
            continue
        parsed = _parse_dates(df[col])
        bad = parsed.notna() & (parsed > as_of_dt)
        checks.append(_make_check(f"{col} is not in the future", "Validity", bad,
                                  f"Date is after the reference date ({as_of_dt.date()})."))
    return checks


def check_validity(
    df: pd.DataFrame,
    email_columns: list[str],
    phone_columns: list[str],
    non_negative_columns: list[str],
    date_columns: list[str],
    no_future_columns: list[str],
    as_of: str | None = None,
) -> list[dict]:
    return (
        _check_emails(df, email_columns)
        + _check_phones(df, phone_columns)
        + _check_non_negative(df, non_negative_columns)
        + _check_dates_parseable(df, date_columns)
        + _check_no_future(df, no_future_columns, as_of)
    )


def check_accuracy(df: pd.DataFrame, range_columns: dict[str, tuple]) -> list[dict]:
    """Reasonableness: a numeric value sits within a sane business range.
    Distinct from validity — a value can be a valid number yet implausible."""
    checks = []
    for col, bounds in range_columns.items():
        if col not in df.columns:
            continue
        lo, hi = bounds
        present = ~_is_blank(df[col])
        numeric = pd.to_numeric(df[col], errors="coerce")
        # only judge values that ARE numbers; non-numeric is a Validity concern
        bad = present & numeric.notna() & ((numeric < lo) | (numeric > hi))
        checks.append(_make_check(f"{col} is within [{lo}, {hi}]", "Accuracy", bad,
                                  f"Value is outside the reasonable range {lo}-{hi}."))
    return checks


def check_conformity(df: pd.DataFrame, allowed_values: dict[str, set]) -> list[dict]:
    """Conformity is case-sensitive: 'active' does not match an allowed 'Active'."""
    checks = []
    for col, allowed in allowed_values.items():
        if col not in df.columns:
            continue
        present = ~_is_blank(df[col])
        bad = present & ~df[col].isin(allowed)
        checks.append(_make_check(f"{col} uses an allowed value", "Conformity", bad,
                                  "Value is outside the approved set."))
    return checks


def check_consistency(df: pd.DataFrame, ordered_dates: list[tuple[str, str]]) -> list[dict]:
    checks = []
    for earlier, later in ordered_dates:
        if earlier not in df.columns or later not in df.columns:
            continue
        a = _parse_dates(df[earlier])
        b = _parse_dates(df[later])
        both = a.notna() & b.notna()
        bad = both & (b < a)
        checks.append(_make_check(f"{later} is on/after {earlier}", "Consistency", bad,
                                  f"{later} occurs before {earlier}."))
    return checks


def check_integrity(df: pd.DataFrame, reference_columns: list[dict]) -> list[dict]:
    """Referential integrity: every non-blank value in a child column must
    reference an existing value in its parent column."""
    checks = []
    for ref in reference_columns:
        child = ref.get("column")
        parent = ref.get("references")
        if not child or not parent or child not in df.columns or parent not in df.columns:
            continue
        valid_keys = set(df[parent][~_is_blank(df[parent])].astype(str))
        present = ~_is_blank(df[child])
        bad = present & ~df[child].astype(str).isin(valid_keys)
        checks.append(_make_check(f"{child} references an existing {parent}", "Integrity", bad,
                                  f"Value does not match any existing {parent}."))
    return checks


def check_timeliness(df: pd.DataFrame, timeliness: dict | None, as_of: str | None = None) -> list[dict]:
    if not timeliness:
        return []
    col = timeliness.get("column")
    max_age = int(float(timeliness.get("max_age_days", 365)))  # tolerate "30" or "30.0"
    if not col or col not in df.columns:
        return []
    as_of_dt = _as_of_datetime(as_of)
    parsed = _parse_dates(df[col])
    age_days = (as_of_dt - parsed).dt.days
    bad = parsed.notna() & (age_days > max_age)
    return [_make_check(f"{col} is fresh (<= {max_age} days)", "Timeliness", bad,
                        f"Record older than {max_age} days as of {as_of_dt.date()}.")]


# --------------------------------------------------------------------------- #
# Profiling + orchestration
# --------------------------------------------------------------------------- #
def profile_columns(df: pd.DataFrame) -> list[dict]:
    rows = []
    n = len(df)
    for col in df.columns:
        blanks = int(_is_blank(df[col]).sum())
        non_blank = df[col][~_is_blank(df[col])]
        unique = int(non_blank.nunique())
        samples = [str(v) for v in non_blank.drop_duplicates().head(3)]
        rows.append({
            "column": col,
            "dtype": str(df[col].dtype),
            "nulls": blanks,
            "null_pct": round(100 * blanks / n, 1) if n else 0.0,
            "unique": unique,
            "unique_pct": round(100 * unique / n, 1) if n else 0.0,
            "samples": samples,
        })
    return rows


def _dimension_score(checks: list[dict]) -> float | None:
    total = sum(c["total"] for c in checks)
    passed = sum(c["passed"] for c in checks)
    if total == 0:
        return None
    return round(100 * passed / total, 1)


def _build_dimensions(grouped: dict[str, list[dict]], weights: dict) -> tuple[dict, list, float | None]:
    """Tag each check with its category (without mutating the originals), score
    each dimension, and compute the weighted overall score."""
    dimensions: dict[str, dict] = {}
    categories: list[dict] = []
    weighted_sum = 0.0
    weight_total = 0.0
    for name, checks in grouped.items():
        category = DIMENSION_CATEGORY.get(name, name)
        tagged = [{**c, "category": category} for c in checks]  # new dicts, no mutation
        score = _dimension_score(tagged)
        weight = float(weights.get(name, 1.0))
        dimensions[name] = {"score": score, "weight": weight, "category": category, "checks": tagged}
        affected = {r for c in tagged for r in c["failing_rows"]}
        categories.append({
            "category": category,
            "dimension": name,
            "score": score,
            "flagged_checks": sum(c["failed"] for c in tagged),
            "affected_rows": len(affected),
        })
        if score is not None:
            weighted_sum += score * weight
            weight_total += weight
    overall = round(weighted_sum / weight_total, 1) if weight_total else None
    return dimensions, categories, overall


def load_csv(source: Union[str, Path, IO[bytes]]) -> pd.DataFrame:
    """Read a CSV treating blank cells as empty strings (not NaN).

    keep_default_na=False gives every column a stable string dtype.
    skip_blank_lines=False keeps blank/whitespace-only rows so an entirely empty
    record is still counted and flagged (not silently dropped).
    """
    df = pd.read_csv(source, dtype=str, keep_default_na=False, skip_blank_lines=False)
    return df.reset_index(drop=True)  # guarantee a clean positional index


def run_quality_report(df: pd.DataFrame, schema: dict, as_of: str | None = None) -> dict:
    """Run every configured check and return a structured quality report."""
    if df is None or df.empty:
        raise ValueError("No data to assess: the dataset is empty.")

    as_of = as_of or schema.get("as_of")
    grouped: dict[str, list[dict]] = {
        "Completeness": check_completeness(df, schema.get("required_columns", [])),
        "Uniqueness": check_uniqueness(df, schema.get("unique_columns", [])),
        "Validity": check_validity(
            df,
            schema.get("email_columns", []),
            schema.get("phone_columns", []),
            schema.get("non_negative_columns", []),
            schema.get("date_columns", []),
            schema.get("no_future_columns", []),
            as_of,
        ),
        "Accuracy": check_accuracy(df, schema.get("range_columns", {})),
        "Conformity": check_conformity(df, schema.get("allowed_values", {})),
        "Consistency": check_consistency(df, schema.get("ordered_dates", [])),
        "Integrity": check_integrity(df, schema.get("reference_columns", [])),
        "Timeliness": check_timeliness(df, schema.get("timeliness"), as_of),
    }
    dimensions, categories, overall = _build_dimensions(grouped, schema.get("weights", {}))

    return {
        "as_of": str(_as_of_datetime(as_of).date()),
        "row_count": int(len(df)),
        "column_count": int(df.shape[1]),
        "overall_score": overall,
        "dimensions": dimensions,
        "categories": categories,
        "profile": profile_columns(df),
    }
