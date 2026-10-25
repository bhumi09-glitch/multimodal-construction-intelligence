"""Headless UI smoke tests using Streamlit's AppTest. Run: python -m pytest -q"""
import os

import pytest
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(__file__), "..", "app.py")


@pytest.fixture(autouse=True)
def no_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def fresh():
    return AppTest.from_file(APP, default_timeout=30).run()


def test_starts_without_api_key_in_demo_mode():
    at = fresh()
    assert not at.exception
    assert any("Demo Mode Active" in m.value for m in at.markdown)


@pytest.mark.parametrize("page", ["Overview", "Site Safety & PPE Audit", "Crack Diagnostics", "Planning & Valuation",
                                  "Daily Site Assistant", "Project Report"])
def test_every_page_renders(page):
    at = fresh()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]


def test_analyse_without_image_shows_error_not_fake_result():
    at = fresh()
    at.sidebar.radio[0].set_value("Site Safety & PPE Audit").run()
    at.button(key="safety_run").click().run()
    assert not at.exception
    assert any("Upload a valid image" in e.value for e in at.error)


def test_planning_calculates_and_updates():
    at = fresh()
    at.sidebar.radio[0].set_value("Planning & Valuation").run()
    assert not at.exception
    labels = [m.label for m in at.metric]
    assert "Estimated total budget" in labels
    at.slider(key="plan_completion").set_value(100).run()
    assert not at.exception
    assert at.session_state["results"]["valuation"]["data"]["inputs"]["completion_percent"] == 100


def test_chatbot_and_weather():
    at = fresh()
    at.sidebar.radio[0].set_value("Daily Site Assistant").run()
    at.selectbox(key="weather_select").set_value("Heavy Rain").run()
    assert at.session_state["weather"] == "Heavy Rain"
    at.chat_input[0].set_value("What should I check before concrete pouring?").run()
    assert not at.exception
    assert any("formwork" in m["content"].lower() for m in at.session_state["chat"])


def test_invalid_api_key_input_does_not_crash():
    at = fresh()
    at.sidebar.text_input[0].set_value("not-a-real-key").run()
    at.sidebar.button[0].click().run()
    assert not at.exception
