"""Unit tests for pure-Python logic (no API key or network needed). Run: python -m pytest -q"""
import io

import pytest
from PIL import Image

from modules import crack_analysis, safety_analysis, valuation, weather_advisor
from modules.construction_assistant import answer_question, demo_answer
from modules.gemini_service import GeminiService, GeminiServiceError
from modules.report_generator import build_consolidated_report, to_json_bytes
from utils.image_utils import load_uploaded_image
from utils.json_utils import extract_json


# ---- JSON utilities -------------------------------------------------------
def test_extract_json_plain_fenced_and_prose():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here it is: {"a": 1} Hope that helps') == {"a": 1}


def test_extract_json_repairs_common_errors():
    assert extract_json('{"a": 1, "b": [1, 2,],}') == {"a": 1, "b": [1, 2]}
    assert extract_json('{"a": 1, "b": [1, 2') == {"a": 1, "b": [1, 2]}  # truncated
    assert extract_json('{"a": True, "b": None}') == {"a": True, "b": None}


@pytest.mark.parametrize("bad", [None, "", "no json here", "[1,2,3]", 42])
def test_extract_json_never_raises(bad):
    assert extract_json(bad) is None


# ---- contracts -------------------------------------------------------------
def test_safety_validation_clamps_and_fills_defaults():
    out = safety_analysis.validate_safety_result({"safety_score": 250, "hazards": [{"hazard": "x", "severity": "bogus"}],
                                                  "ppe_detection": {"helmet": {"status": "detected", "confidence": "95%"}}})
    assert out["safety_score"] == 100
    assert out["ppe_detection"]["helmet"] == {"status": "Detected", "confidence": 95}
    assert out["ppe_detection"]["safety_harness"]["status"] == "Unclear"
    assert out["hazards"][0]["severity"] == "Medium"
    assert out["overall_status"] in safety_analysis.OVERALL_STATUSES
    assert set(out) == {"safety_score", "overall_status", "ppe_detection", "hazards", "recommendations"}


def test_crack_validation_contract_keys_and_choices():
    out = crack_analysis.validate_crack_result({"defect_type": "spalling", "severity": "HIGH", "estimated_crack_width_mm": "3.5 mm"})
    assert out["defect_type"] == "Spalling" and out["severity"] == "High" and out["estimated_crack_width_mm"] == 3.5
    assert set(out) == {"defect_type", "severity", "estimated_crack_width_mm", "visual_observations",
                        "possible_root_causes", "recommended_repairs", "urgency", "confidence"}


def test_all_demo_scenarios_are_valid():
    for i in range(16):
        seed = f"{i:08x}"
        s = safety_analysis.demo_safety_result(seed)
        assert 0 <= s["safety_score"] <= 100 and s["hazards"]
        c = crack_analysis.demo_crack_result(seed)
        assert c["defect_type"] in crack_analysis.DEFECT_TYPES


# ---- run_analysis fallbacks --------------------------------------------------
class FakeService:
    def __init__(self, reply=None, error=None):
        self.reply, self.error = reply, error

    def generate(self, *a, **k):
        if self.error:
            raise self.error
        return self.reply


def _run(service):
    return safety_analysis.analyze_site_image(service, object(), "abcd1234")


def test_no_service_is_demo_mode():
    result, mode, notice = _run(None)
    assert mode == "demo" and notice is None and result["hazards"]


def test_live_valid_json_and_malformed_json_and_errors():
    good = '```json\n{"safety_score": 77, "overall_status": "Partial Compliance", "hazards": [], "ppe_detection": {}}\n```'
    result, mode, _ = _run(FakeService(good))
    assert mode == "live" and result["safety_score"] == 77
    _, mode, notice = _run(FakeService("totally not json"))
    assert mode == "demo" and "could not be read" in notice
    _, mode, notice = _run(FakeService(error=GeminiServiceError("Gemini rate limit")))
    assert mode == "demo" and "rate limit" in notice
    _, mode, notice = _run(FakeService(error=RuntimeError("boom")))
    assert mode == "demo" and "unexpected" in notice.lower()


def test_blank_key_means_demo_not_error():
    assert GeminiService.create("   ") == (None, None)
    assert GeminiService.create(None) == (None, None)


# ---- valuation ----------------------------------------------------------------
def test_valuation_math():
    v = valuation.compute_valuation("Residential", 2000, "Tier 2", 50, "Standard", 0)
    assert v["total_project_budget_inr"] == 2000 * 1900
    assert v["capital_expenditure_incurred_inr"] == v["total_project_budget_inr"] // 2
    assert v["steel_requirement_tonnes"] == 8.0 and v["cement_requirement_bags"] == 800
    assert v["current_market_asset_valuation_inr"] == round(v["total_project_budget_inr"] * 1.7 * 0.5)


@pytest.mark.parametrize("args", [("Residential", 0, "Tier 1", 10), ("Residential", -5, "Tier 1", 10),
                                  ("Residential", 1000, "Tier 1", 101), ("Castle", 1000, "Tier 1", 10),
                                  ("Residential", "abc", "Tier 1", 10), ("Residential", 1000, "Tier 9", 10),
                                  ("Residential", float("nan"), "Tier 1", 10)])
def test_valuation_rejects_invalid_input(args):
    with pytest.raises(ValueError):
        valuation.compute_valuation(*args)


def test_format_inr_units():
    assert valuation.format_inr(950) == "\u20b9950"
    assert valuation.format_inr(250000) == "\u20b92.50 Lakh"
    assert valuation.format_inr(32_500_000) == "\u20b93.25 Crore"


def test_milestones_and_prompt():
    rows = valuation.milestone_status(50)
    assert [r["state"] for r in rows] == ["Complete", "Complete", "In progress", "Not started", "Not started", "Not started"]
    p = valuation.build_architectural_prompt("Commercial", 8000, "Tier 1", 70, "glass facade")
    assert "commercial" in p and "70%" in p and "glass facade" in p


# ---- weather / assistant / reports ----------------------------------------------
@pytest.mark.parametrize("cond", weather_advisor.CONDITIONS)
def test_every_weather_condition_has_full_advisory(cond):
    a = weather_advisor.get_advisory(cond)
    assert all(a[k] for k in ("safety_alerts", "recommended_actions", "prohibited_activities", "daily_checklist"))
    assert a["condition"] == cond


def test_unknown_weather_falls_back_to_normal():
    assert weather_advisor.get_advisory("Tornado")["condition"] == "Normal"


def test_demo_chatbot_answers():
    assert "excavation" in demo_answer("What precautions should I take during heavy rain?").lower()
    assert "formwork" in demo_answer("What should I check before concrete pouring?").lower()
    assert "settlement" in demo_answer("Why are cracks appearing on this wall?").lower()
    assert "I can help" in demo_answer("tell me a joke about bananas")
    reply, mode, _ = answer_question(None, "", [])
    assert mode == "demo" and reply
    reply, mode, notice = answer_question(FakeService(error=GeminiServiceError("down")), "heat?", [])
    assert mode == "demo" and notice


def test_reports_serialise():
    entry = {"data": safety_analysis.demo_safety_result(), "mode": "demo", "source_name": "x.jpg", "timestamp": "t"}
    report = build_consolidated_report({"safety": entry, "crack": None, "valuation": None})
    assert report["demonstration_notice"] and report["modules_completed"] == ["ppe_safety_audit"]
    assert b"consolidated_project_report" in to_json_bytes(report)


# ---- image validation -------------------------------------------------------------
class Upload:
    def __init__(self, name, data):
        self.name, self._d = name, data

    def getvalue(self):
        return self._d


def _png(size=(100, 80)):
    buf = io.BytesIO()
    Image.new("RGB", size, "gray").save(buf, "PNG")
    return buf.getvalue()


def test_image_validation():
    img, err, h = load_uploaded_image(Upload("a.png", _png()))
    assert img is not None and err is None and len(h) == 32
    assert load_uploaded_image(None)[1]
    assert "Unsupported" in load_uploaded_image(Upload("a.gif", _png()))[1]
    assert "empty" in load_uploaded_image(Upload("a.png", b""))[1]
    assert "not a valid image" in load_uploaded_image(Upload("a.jpg", b"not an image"))[1]
    assert "too small" in load_uploaded_image(Upload("a.png", _png((10, 10))))[1]
    assert "10 MB" in load_uploaded_image(Upload("a.png", b"0" * (10 * 1024 * 1024 + 1)))[1]
