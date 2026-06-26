# 🛡️ Data Quality & Governance Dashboard

Score any dataset for data quality the way a governance team actually does — across the **eight standard data-quality dimensions** — then drill into the exact records that fail each rule.

> **Live demo:** _add your Streamlit Cloud link here after deploy_
> **Built with:** Python · pandas · Streamlit · pytest — **no external APIs, no keys; your data never leaves the app.**

---

## Why this exists

Bad master data quietly breaks reporting, billing, compliance, and analytics. Governance teams manage it by measuring data against a small number of well-understood **quality dimensions** and tracking a score over time. This tool makes that measurement concrete and interactive: point it at a CSV and it tells you *how good the data is, where it breaks, and which rows to fix first*.

## What it does

- **Scores eight dimensions** and rolls them into one weighted **Data Quality Score (0–100)**:

  | Dimension | Example rules |
  |---|---|
  | **Completeness** | Required fields are populated |
  | **Uniqueness** | No duplicate keys or duplicate records |
  | **Validity** | Emails, phones, numbers, and dates are well-formed; no future-dated events |
  | **Accuracy** | Values are plausible / within reasonable ranges (e.g. age 18–100) |
  | **Conformity** | Values come from an approved set (e.g. country, status) |
  | **Consistency** | Cross-field logic holds (e.g. `last_active ≥ signup`) |
  | **Integrity** | Referenced records exist (referential integrity) |
  | **Timeliness** | Records are fresh, not stale |

- **Profiles every column** — type, null %, uniqueness, sample values.
- **Drills into failures** — pick any failing rule and see the exact offending rows.
- **Exports a quality report** as CSV for sharing or tracking over time.
- **Works on your own data** — upload any CSV and the tool infers a conservative rule set automatically; or use the bundled sample to see the full, hand-authored governance rule set in action.

## Screenshots

![Data Quality & Governance Dashboard — overview](screenshots/01-overview.png)

The overall score, discrepancy categories (missing / duplicate / invalid / implausible / non-conforming / inconsistent / orphaned / stale), per-rule results, and row-level drill-down — in a dark, data-dense layout.

## Quickstart

```bash
git clone https://github.com/adeebansar/data-governance-dashboard.git
cd data-governance-dashboard

python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

streamlit run app.py
```

Regenerate the sample dataset (optional):

```bash
python sample_data/generate_sample.py
```

## Testing

The rule engine is covered by unit tests that validate it against a sample dataset with **known, planted issues** — so every dimension is checked against ground truth. A smoke test boots the Streamlit app headlessly.

```bash
python -m pytest -q
```

## How it's built

```
app.py                 # Streamlit UI (presentation only)
data_quality.py        # Pure-function rule engine + column profiling
rules_config.py        # Declarative rules: rich schema for the sample + auto-inference for any CSV
sample_data/           # Synthetic 'messy customer master' + its generator
tests/                 # Engine tests (ground-truth) + app smoke test
```

The engine is deliberately separated from the UI: every check is a pure function returning plain data, which keeps it testable and reusable (a CLI or scheduled job could call the same engine).

## License

MIT — see [LICENSE](LICENSE).
