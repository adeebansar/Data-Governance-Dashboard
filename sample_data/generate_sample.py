"""Generate a synthetic 'customer master' dataset with deliberately planted
data-quality issues.

Why this exists: a credible data-quality tool must be validated against data
whose problems are *known in advance*. This generator plants a fixed, documented
set of issues so the rule engine's output can be checked against ground truth
(see tests/test_data_quality.py). Output is deterministic — no randomness — so
the demo and the tests are reproducible.

Run:  python sample_data/generate_sample.py
"""

from __future__ import annotations

import csv
from pathlib import Path

OUTPUT = Path(__file__).with_name("customer_master_messy.csv")

HEADER = [
    "customer_id",
    "full_name",
    "email",
    "phone",
    "country",
    "age",
    "signup_date",
    "last_active_date",
    "annual_revenue",
    "referred_by",
    "status",
]

ALLOWED_COUNTRIES = {"United States", "Canada", "United Kingdom", "India", "Germany"}
ALLOWED_STATUS = {"Active", "Inactive", "Churned"}


def clean_rows() -> list[list[str]]:
    """28 well-formed records — the 'good' baseline."""
    countries = ["United States", "Canada", "United Kingdom", "India", "Germany"]
    statuses = ["Active", "Inactive", "Churned"]
    rows: list[list[str]] = []
    for i in range(1, 29):
        rows.append(
            [
                f"C{i:04d}",
                f"Firstname{i} Lastname{i}",
                f"user{i}@example.com",
                f"+1-555-{i:03d}-{1000 + i:04d}",
                countries[i % len(countries)],
                str(25 + (i % 40)),                 # plausible age 25–64
                "2024-03-15",
                "2026-05-20",
                str(50000 + i * 1000),
                "" if i == 1 else "C0001",          # valid referral (or none)
                statuses[i % len(statuses)],
            ]
        )
    return rows


# Each messy row documents the issue(s) it plants, by dimension. Reference
# "today" for timeliness/future checks is 2026-06-26. Columns kept otherwise
# valid (age 40, referral C0001) so each row trips only its intended issue.
MESSY_ROWS: list[list[str]] = [
    # completeness: missing email
    ["C0029", "Grace Hopper", "", "+1-555-200-2001", "United States", "40", "2024-01-10", "2026-04-01", "72000", "C0001", "Active"],
    # completeness: missing full_name
    ["C0030", "", "ada@example.com", "+1-555-201-2002", "Canada", "40", "2024-02-11", "2026-04-02", "61000", "C0001", "Active"],
    # completeness: missing annual_revenue
    ["C0031", "Alan Turing", "alan@example.com", "+1-555-202-2003", "United Kingdom", "40", "2024-02-12", "2026-04-03", "", "C0001", "Inactive"],
    # uniqueness: duplicate customer_id (C0001 already exists)
    ["C0001", "Linus Pauling", "linus@example.com", "+1-555-203-2004", "Germany", "40", "2024-02-13", "2026-04-04", "88000", "C0001", "Active"],
    # uniqueness: duplicate email (user5@example.com already exists)
    ["C0032", "Marie Curie", "user5@example.com", "+1-555-204-2005", "India", "40", "2024-02-14", "2026-04-05", "90000", "C0001", "Active"],
    # validity: malformed email
    ["C0033", "Niels Bohr", "niels.bohr.example.com", "+1-555-205-2006", "Germany", "40", "2024-02-15", "2026-04-06", "77000", "C0001", "Active"],
    # validity: malformed phone
    ["C0034", "Rosalind Franklin", "rosalind@example.com", "555 2006", "United Kingdom", "40", "2024-02-16", "2026-04-07", "65000", "C0001", "Inactive"],
    # validity: negative revenue
    ["C0035", "Enrico Fermi", "enrico@example.com", "+1-555-206-2007", "India", "40", "2024-02-17", "2026-04-08", "-15000", "C0001", "Active"],
    # validity: unparseable signup_date
    ["C0036", "Lise Meitner", "lise@example.com", "+1-555-207-2008", "Germany", "40", "not-a-date", "2026-04-09", "54000", "C0001", "Active"],
    # conformity: country not in allowed set
    ["C0037", "Paul Dirac", "paul@example.com", "+1-555-208-2009", "usa", "40", "2024-02-18", "2026-04-10", "59000", "C0001", "Active"],
    # conformity: status not in allowed set
    ["C0038", "Max Planck", "max@example.com", "+1-555-209-2010", "Germany", "40", "2024-02-19", "2026-04-11", "63000", "C0001", "actv"],
    # consistency: last_active_date before signup_date
    ["C0039", "Erwin Schrodinger", "erwin@example.com", "+1-555-210-2011", "United States", "40", "2024-06-01", "2024-01-01", "70000", "C0001", "Active"],
    # validity: future signup_date (after 2026-06-26)
    ["C0040", "Werner Heisenberg", "werner@example.com", "+1-555-211-2012", "Germany", "40", "2027-01-01", "2027-02-01", "81000", "C0001", "Active"],
    # timeliness: stale last_active_date (very old)
    ["C0041", "Dmitri Mendeleev", "dmitri@example.com", "+1-555-212-2013", "India", "40", "2019-01-01", "2019-06-01", "48000", "C0001", "Inactive"],
    # integrity: orphaned referral (C9999 does not exist)
    ["C0042", "Katherine Johnson", "katherine@example.com", "+1-555-213-2014", "United States", "35", "2024-03-01", "2026-04-12", "67000", "C9999", "Active"],
    # accuracy: implausible age (too high)
    ["C0043", "Tu Youyou", "tu@example.com", "+1-555-214-2015", "Germany", "250", "2024-03-02", "2026-04-13", "71000", "C0001", "Active"],
    # accuracy: implausible age (too low for an 18+ customer base)
    ["C0044", "John Bardeen", "johnb@example.com", "+1-555-215-2016", "Canada", "7", "2024-03-03", "2026-04-14", "69000", "C0001", "Active"],
]


def write_csv() -> Path:
    rows = clean_rows() + MESSY_ROWS
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return OUTPUT


if __name__ == "__main__":
    path = write_csv()
    total = len(clean_rows()) + len(MESSY_ROWS)
    print(f"Wrote {path} ({total} rows: 28 clean + {len(MESSY_ROWS)} with planted issues)")
    print("Planted issues by category:")
    print("  Missing data       : 3 (email, name, revenue)")
    print("  Duplicate data     : 2 (duplicate id, duplicate email)")
    print("  Invalid data       : 5 (bad email, bad phone, negative revenue, bad date, future date)")
    print("  Non-conforming data: 2 (bad country, bad status)")
    print("  Inconsistent data  : 1 (last_active before signup)")
    print("  Stale data         : 1 (last_active 2019)")
    print("  Orphaned data      : 1 (referral to non-existent customer)")
    print("  Implausible data   : 2 (age 250, age 7)")
