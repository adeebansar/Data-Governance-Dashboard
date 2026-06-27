"""Data Quality & Governance Dashboard — Streamlit UI (premium dark theme).

Upload any CSV (or use the bundled sample) to score it across the eight standard
data-quality dimensions, see discrepancies grouped by plain-language category
(missing / duplicate / invalid / ...), and drill into the exact failing rows.
No external APIs, no keys — your data never leaves the app.

Security note: values derived from the uploaded file (column names, cell values,
file name) are only rendered through native Streamlit widgets or HTML-escaped
before injection. Raw HTML is built from our own constants + numbers.
"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

import ai_risk
import data_quality as dq
from rules_config import CUSTOMER_MASTER_SCHEMA, SAMPLE_AS_OF, infer_schema

SAMPLE_PATH = Path(__file__).with_name("sample_data") / "customer_master_messy.csv"

st.set_page_config(
    page_title="Data & AI Governance Dashboard",
    page_icon="🛡️",
    layout="wide",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&family=Great+Vibes&display=swap');

:root{
  --bg:#0A0B10; --surface:rgba(255,255,255,.035); --surface-2:#14161E;
  --line:rgba(255,255,255,.08); --line-strong:rgba(255,255,255,.14);
  --text:#F3F4F6; --muted:#9AA1AC; --dim:#6B7280;
  --gold:#E5B567; --gold-soft:rgba(229,181,103,.14);
  --good:#34D399; --warn:#FBBF24; --bad:#F87171;
  --good-bg:rgba(52,211,153,.12); --warn-bg:rgba(251,191,36,.12); --bad-bg:rgba(248,113,113,.12);
}
.stApp{
  background:
    radial-gradient(1100px 520px at 12% -8%, rgba(229,181,103,.10), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(59,130,246,.08), transparent 55%),
    var(--bg);
}
html, body, [class*="css"], .stApp, .stMarkdown{ font-family:'Fira Sans', system-ui, sans-serif; }
.block-container{ padding-top:1.6rem; max-width:1240px; }
.mono{ font-family:'Fira Code', monospace; font-variant-numeric:tabular-nums; }

/* hero */
.hero{
  position:relative; border:1px solid var(--line); border-radius:20px;
  padding:1.7rem 1.9rem; margin-bottom:1.5rem; overflow:hidden;
  background:linear-gradient(135deg, rgba(229,181,103,.10) 0%, rgba(20,22,30,.6) 40%, rgba(10,11,16,.85) 100%);
}
.hero::before{ content:""; position:absolute; left:0; top:0; bottom:0; width:3px;
  background:linear-gradient(180deg,var(--gold),transparent); }
.hero .eyebrow{ color:var(--gold); font-size:.72rem; font-weight:600;
  letter-spacing:.22em; text-transform:uppercase; }
.hero h1{ margin:.35rem 0 0; font-size:1.78rem; font-weight:700; letter-spacing:-.02em; color:var(--text); }
.hero .meta{ margin-top:.45rem; color:var(--muted); font-size:.92rem; }
.hero .meta b{ color:var(--text); font-weight:600; }

/* cards */
.card{
  border:1px solid var(--line); border-radius:16px; padding:1.05rem 1.15rem;
  background:var(--surface); height:100%; transition:border-color .2s ease, transform .2s ease;
  backdrop-filter:blur(6px);
}
.card:hover{ border-color:var(--line-strong); transform:translateY(-2px); }
.lbl{ font-size:.7rem; text-transform:uppercase; letter-spacing:.12em; color:var(--muted); font-weight:600; }
.val{ font-size:1.7rem; font-weight:700; line-height:1.05; margin-top:.3rem; }
.sub{ color:var(--dim); font-size:.82rem; margin-top:.25rem; }

/* score hero card */
.score-card{ text-align:left; }
.score{ font-size:3.6rem; font-weight:700; line-height:1; letter-spacing:-.03em; }
.score .denom{ font-size:1.15rem; color:var(--dim); font-weight:500; }
.ring{ display:inline-block; padding:.12rem .65rem; border-radius:999px; font-size:.72rem;
  font-weight:700; letter-spacing:.04em; margin-top:.5rem; }

/* category tiles */
.cat-name{ font-size:.95rem; font-weight:600; color:var(--text); }
.cat-num{ font-size:1.85rem; font-weight:700; font-family:'Fira Code',monospace;
  font-variant-numeric:tabular-nums; line-height:1.1; margin-top:.2rem; }
.cat-foot{ font-size:.76rem; color:var(--dim); margin-top:.15rem; }
.dot{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:.45rem; vertical-align:middle; }

.good{ color:var(--good);} .warn{ color:var(--warn);} .bad{ color:var(--bad);} .gold{ color:var(--gold);}
.bg-good{ background:var(--good-bg); color:var(--good);}
.bg-warn{ background:var(--warn-bg); color:var(--warn);}
.bg-bad{ background:var(--bad-bg); color:var(--bad);}
.dot.good{ background:var(--good);} .dot.warn{ background:var(--warn);} .dot.bad{ background:var(--bad);}

.section{ font-size:1.05rem; font-weight:600; color:var(--text); letter-spacing:-.01em;
  margin:.4rem 0 .2rem; }
.section .hint{ color:var(--dim); font-weight:400; font-size:.85rem; }
hr{ border-color:var(--line) !important; }
[data-testid="stHeader"], [data-testid="stToolbar"]{ display:none; }
.footer-sign{ margin-top:1.4rem; padding-top:1.1rem; border-top:1px solid var(--line);
  display:flex; align-items:flex-end; justify-content:space-between; flex-wrap:wrap; gap:.8rem; }
.footer-sign .meta-cap{ color:var(--dim); font-size:.8rem; max-width:60%; }
.sign-wrap{ text-align:right; }
.sign-label{ color:var(--muted); font-size:.68rem; letter-spacing:.14em; text-transform:uppercase; }
.signature{ font-family:'Great Vibes', cursive; color:var(--gold); font-size:2.5rem; line-height:1;
  margin-top:-.1rem; text-shadow:0 0 20px rgba(229,181,103,.28); }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
def _band(score: float | None) -> str:
    if score is None:
        return "warn"
    if score >= 90:
        return "good"
    if score >= 70:
        return "warn"
    return "bad"


def _fmt(score: float | None) -> str:
    return "n/a" if score is None else f"{score:g}"


def load_source() -> tuple[pd.DataFrame, dict, str, str]:
    """Sidebar data picker. Returns (df, schema, as_of, source_label)."""
    st.sidebar.markdown("### Data source")
    choice = st.sidebar.radio(
        "Assess which dataset?",
        ["Sample: messy customer master", "Upload my own CSV"],
        label_visibility="collapsed",
    )
    if choice.startswith("Sample"):
        df = dq.load_csv(SAMPLE_PATH)
        st.sidebar.caption(
            "Synthetic master-data table with 17 deliberately planted issues "
            "across all eight quality dimensions."
        )
        return df, CUSTOMER_MASTER_SCHEMA, SAMPLE_AS_OF, "Sample customer master"

    upload = st.sidebar.file_uploader("Upload a CSV", type=["csv"])
    if upload is None:
        st.info("⬅️ Upload a CSV in the sidebar, or switch to the sample dataset to see the tool in action.")
        st.stop()
    try:
        df = dq.load_csv(upload)
    except Exception as exc:  # noqa: BLE001 — surface any parse error to the user
        st.error(f"Could not read that CSV: {exc}")
        st.stop()
    if df.empty or df.shape[1] == 0:
        st.error("That file has no rows or no columns to assess.")
        st.stop()
    as_of = st.sidebar.date_input("Reference date ('today')", value=date.today()).isoformat()
    return df, infer_schema(df, as_of), as_of, upload.name


def render_hero(source_label: str, report: dict) -> None:
    safe = html.escape(source_label)
    st.markdown(
        f"""
        <div class="hero">
          <div class="eyebrow">Data Governance · AI Risk · Quality</div>
          <h1>🛡️ Data &amp; AI Governance Dashboard</h1>
          <div class="meta">Source <b>{safe}</b> &nbsp;·&nbsp;
            <span class="mono">{report['row_count']}</span> rows ×
            <span class="mono">{report['column_count']}</span> columns &nbsp;·&nbsp;
            assessed as of <b>{report['as_of']}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _rows_with_any_issue(report: dict) -> int:
    bad: set[int] = set()
    for d in report["dimensions"].values():
        for c in d["checks"]:
            bad.update(c["failing_rows"])
    return len(bad)


def render_topline(report: dict) -> None:
    total_issues = sum(c["failed"] for d in report["dimensions"].values() for c in d["checks"])
    overall = report["overall_score"]
    band = _band(overall)
    label = {"good": "Healthy", "warn": "Needs attention", "bad": "At risk"}[band]
    clean = report["row_count"] - _rows_with_any_issue(report)
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(
            f"""<div class="card score-card"><div class="lbl">Overall data quality score</div>
            <div class="score mono {band}">{_fmt(overall)}<span class="denom"> / 100</span></div>
            <span class="ring bg-{band}">{label}</span></div>""",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""<div class="card"><div class="lbl">Failing checks</div>
            <div class="val mono bad">{total_issues}</div>
            <div class="sub">records flagged across all rules</div></div>""",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""<div class="card"><div class="lbl">Fully clean rows</div>
            <div class="val mono good">{clean}<span style="color:var(--dim);font-size:1rem"> / {report['row_count']}</span></div>
            <div class="sub">pass every applicable rule</div></div>""",
            unsafe_allow_html=True,
        )


def _category_band(cat: dict) -> str:
    """Severity colour for a discrepancy category: green when clean, red when
    the problem is material, amber otherwise. Driven by issue count, not just
    the cell-level pass rate (so a category WITH issues never looks 'all clear')."""
    if cat["flagged_checks"] == 0:
        return "good"
    if (cat["score"] is not None and cat["score"] < 90) or cat["affected_rows"] >= 5:
        return "bad"
    return "warn"


def render_categories(report: dict) -> None:
    st.markdown(
        '<div class="section">Data discrepancies by category '
        '<span class="hint">— what kind of problem, and how many records</span></div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(3)
    for i, cat in enumerate(report["categories"]):
        band = _category_band(cat)
        with cols[i % 3]:
            st.markdown(
                f"""<div class="card" style="margin-bottom:.85rem">
                <div class="cat-name"><span class="dot {band}"></span>{cat['category']}</div>
                <div class="cat-num {band}">{cat['affected_rows']}</div>
                <div class="cat-foot">{cat['dimension']} dimension · score {_fmt(cat['score'])} ·
                  {cat['flagged_checks']} flagged</div></div>""",
                unsafe_allow_html=True,
            )


def render_dimension_detail(report: dict, df: pd.DataFrame) -> None:
    st.markdown('<div class="section">Rule results &amp; failing records</div>', unsafe_allow_html=True)
    for name, d in report["dimensions"].items():
        flagged = sum(c["failed"] for c in d["checks"])
        label = f"{d['category']}  ·  {name} — score {_fmt(d['score'])}  ·  {flagged} flagged"
        with st.expander(label, expanded=False):
            if not d["checks"]:
                st.caption("No rules of this type applied to this dataset.")
                continue
            table = pd.DataFrame([
                {
                    "Category": c["category"],
                    "Rule": c["name"],
                    "Pass rate": f"{c['pass_rate'] * 100:.1f}%",
                    "Failing": c["failed"],
                    "What it means": c["detail"],
                }
                for c in d["checks"]
            ])
            st.dataframe(table, hide_index=True, use_container_width=True)

            failing_checks = [c for c in d["checks"] if c["failed"]]
            if failing_checks:
                pick = st.selectbox(
                    "Inspect the rows that failed:",
                    options=[c["name"] for c in failing_checks],
                    key=f"pick_{name}",
                )
                chosen = next(c for c in failing_checks if c["name"] == pick)
                st.dataframe(df.iloc[chosen["failing_rows"]], use_container_width=True)


def render_profile(report: dict) -> None:
    st.markdown('<div class="section">Column profile</div>', unsafe_allow_html=True)
    prof = pd.DataFrame(report["profile"])
    prof["samples"] = prof["samples"].apply(lambda xs: ", ".join(xs))
    prof = prof.rename(columns={
        "column": "Column", "dtype": "Type", "nulls": "Nulls",
        "null_pct": "Null %", "unique": "Unique", "unique_pct": "Unique %",
        "samples": "Sample values",
    })
    st.dataframe(prof, hide_index=True, use_container_width=True)


def _csv_safe(value: str) -> str:
    """Neutralise CSV/Excel formula injection: prefix a leading =, +, -, @ or |."""
    return "'" + value if value and value[0] in "=+-@|" else value


def build_report_csv(report: dict) -> str:
    rows = []
    for name, d in report["dimensions"].items():
        for c in d["checks"]:
            rows.append({
                "category": _csv_safe(c["category"]),
                "dimension": _csv_safe(name),
                "rule": _csv_safe(c["name"]),
                "pass_rate_pct": round(c["pass_rate"] * 100, 1),
                "failing": c["failed"], "total": c["total"],
            })
    return pd.DataFrame(rows).to_csv(index=False)


def _risk_band(level: str) -> str:
    return {"High": "bad", "Medium": "warn", "Low": "good"}.get(level, "warn")


def render_ai_risk(df: pd.DataFrame, sensitive_columns: list) -> None:
    try:
        risk = ai_risk.assess_ai_risk(df, sensitive_columns)
    except ValueError as exc:
        st.error(str(exc))
        return
    band = _risk_band(risk["risk_level"])
    st.markdown(
        f"""<div class="card" style="max-width:360px"><div class="lbl">AI data-risk level</div>
        <div class="score mono {band}" style="font-size:2.4rem">{risk['risk_level']}</div>
        <div class="sub">across personal-data, representation, and readiness checks</div></div>""",
        unsafe_allow_html=True,
    )
    st.write("")

    st.markdown('<div class="section">Personal-data exposure '
                '<span class="hint">— minimise &amp; protect (EU AI Act / GDPR)</span></div>',
                unsafe_allow_html=True)
    if risk["pii"]:
        st.dataframe(pd.DataFrame([
            {"Column": p["column"], "Likely contains": ", ".join(p["categories"])}
            for p in risk["pii"]
        ]), hide_index=True, use_container_width=True)
        st.caption(risk["framework"]["pii"])
    else:
        st.caption("No obvious personal-data columns detected.")

    st.markdown('<div class="section">Representation &amp; bias risk '
                '<span class="hint">— set sensitive attributes in the sidebar</span></div>',
                unsafe_allow_html=True)
    if risk["representation"]:
        for r in risk["representation"]:
            fb = "bad" if r["flags"] else "good"
            note = " · ".join(r["flags"]) if r["flags"] else "balanced"
            st.markdown(
                f'<div class="cat-name" style="margin-top:.5rem"><span class="dot {fb}"></span>'
                f'{r["column"]} <span class="cat-foot" style="display:inline">— {r["groups"]} groups · {note}</span></div>',
                unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(r["distribution"]).rename(
                columns={"value": "Group", "count": "Count", "pct": "% of rows"}),
                hide_index=True, use_container_width=True)
        st.caption(risk["framework"]["representation"])
    else:
        st.caption("Pick one or more sensitive attributes in the sidebar to assess representation.")

    st.markdown('<div class="section">AI-readiness gaps '
                '<span class="hint">— high missingness to resolve before training</span></div>',
                unsafe_allow_html=True)
    if risk["readiness"]:
        st.dataframe(pd.DataFrame([
            {"Column": x["column"], "Missing %": x["null_pct"]} for x in risk["readiness"]
        ]), hide_index=True, use_container_width=True)
        st.caption(risk["framework"]["readiness"])
    else:
        st.caption("No columns exceed the missingness threshold.")


def main() -> None:
    df, schema, as_of, source_label = load_source()
    try:
        report = dq.run_quality_report(df, schema, as_of)
    except Exception as exc:  # noqa: BLE001 — surface any assessment failure to the user
        st.error(f"Could not assess this file: {exc}")
        st.stop()

    cat_cols = [c for c in df.columns if 2 <= df[c].nunique(dropna=True) <= 50]
    default_sens = [c for c in ["country", "gender", "sex", "status", "region", "ethnicity"]
                    if c in df.columns][:2]
    sensitive = st.sidebar.multiselect(
        "Sensitive attributes (bias / representation)", cat_cols, default=default_sens)

    render_hero(source_label, report)
    tab_quality, tab_ai = st.tabs(["Data quality", "AI governance — data risk"])
    with tab_quality:
        render_topline(report)
        st.write("")
        render_categories(report)
        st.divider()
        render_dimension_detail(report, df)
        st.divider()
        render_profile(report)
        st.download_button(
            "⬇️ Download quality report (CSV)",
            data=build_report_csv(report),
            file_name="data_quality_report.csv",
            mime="text/csv",
        )
    with tab_ai:
        render_ai_risk(df, sensitive)
    st.markdown(
        """
        <div class="footer-sign">
          <div class="meta-cap">Data quality + AI data-risk, mapped to NIST AI RMF &amp; the EU AI Act · no external APIs · your data never leaves the app.</div>
          <div class="sign-wrap">
            <div class="sign-label">Built by</div>
            <div class="signature">Adeeb Syed</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
