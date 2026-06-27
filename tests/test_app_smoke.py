"""Smoke test: the Streamlit app boots and renders on the sample dataset
without raising. Uses Streamlit's headless AppTest harness (no browser)."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_app_boots_on_sample_dataset():
    at = AppTest.from_file(str(APP)).run(timeout=60)
    assert not at.exception, f"App raised: {at.exception}"
    # The default sidebar choice is the sample dataset, so a score must render.
    assert any("Governance Dashboard" in str(m.value) for m in at.markdown)
