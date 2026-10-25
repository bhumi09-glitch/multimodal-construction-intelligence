"""EPIC 2 - Site Safety & PPE audit: prompt, JSON contract, validation, demo data."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from modules.gemini_service import GeminiService, run_analysis
from utils.json_utils import as_dict, choice, clamp_number, str_list, text

SEVERITIES = ["Low", "Medium", "High", "Critical"]
PPE_STATUSES = ["Detected", "Not Detected", "Unclear"]
OVERALL_STATUSES = ["Compliant", "Partial Compliance", "Non-Compliant", "Critical Risk"]
PPE_ITEMS = {
    "helmet": "Safety helmet",
    "high_visibility_vest": "High-visibility vest",
    "steel_toe_boots": "Steel-toe boots",
    "safety_harness": "Safety harness",
}
DISCLAIMER = (
    "AI-assisted assessment for awareness and training only. It is not a professional safety "
    "certification or a legal OSHA/IS compliance audit. A qualified safety officer must verify the site."
)

PROMPT = """You are an assistant to a construction safety officer. Inspect this construction-site photo.
Safety context: OSHA 29 CFR 1926 (construction safety: head, foot, fall protection, hazard communication)
and Indian practice (IS 456 for concrete work, IS 3764 excavation safety, IS 4130 demolition safety).
Check: safety helmets, high-visibility vests, steel-toe boots, safety harnesses, general worker safety,
and any visible site hazards.

Rules:
- Report ONLY what is visible. If no workers are visible, or an item cannot be seen, use status "Unclear"
  with a low confidence and say so in the recommendations. Do not invent detections.
- status values: "Detected", "Not Detected", "Unclear". confidence is 0-100.
- safety_score is 0-100 (100 = no concerns). overall_status is one of
  "Compliant", "Partial Compliance", "Non-Compliant", "Critical Risk".
- hazard severity is one of "Low", "Medium", "High", "Critical".

Return ONLY valid JSON, no markdown, in exactly this structure:
{"safety_score": 0, "overall_status": "",
 "ppe_detection": {"helmet": {"status": "", "confidence": 0},
   "high_visibility_vest": {"status": "", "confidence": 0},
   "steel_toe_boots": {"status": "", "confidence": 0},
   "safety_harness": {"status": "", "confidence": 0}},
 "hazards": [{"hazard": "", "severity": "", "description": "", "corrective_action": ""}],
 "recommendations": []}"""


def status_from_score(score: float) -> str:
    if score >= 85:
        return "Compliant"
    if score >= 60:
        return "Partial Compliance"
    if score >= 35:
        return "Non-Compliant"
    return "Critical Risk"


def validate_safety_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce any dict into the full PPE JSON contract (always complete, always valid)."""
    score = round(clamp_number(raw.get("safety_score"), 0, 100, 0))
    ppe_raw = as_dict(raw.get("ppe_detection"))
    ppe = {}
    for key in PPE_ITEMS:
        item = as_dict(ppe_raw.get(key))
        ppe[key] = {
            "status": choice(item.get("status"), PPE_STATUSES, "Unclear"),
            "confidence": round(clamp_number(item.get("confidence"), 0, 100, 0)),
        }
    hazards = []
    for h in (raw.get("hazards") if isinstance(raw.get("hazards"), list) else [])[:12]:
        h = as_dict(h)
        if not text(h.get("hazard")):
            continue
        hazards.append({
            "hazard": text(h.get("hazard")),
            "severity": choice(h.get("severity"), SEVERITIES, "Medium"),
            "description": text(h.get("description"), "No description provided."),
            "corrective_action": text(h.get("corrective_action"), "Review with the site safety officer."),
        })
    return {
        "safety_score": score,
        "overall_status": choice(raw.get("overall_status"), OVERALL_STATUSES, status_from_score(score)),
        "ppe_detection": ppe,
        "hazards": hazards,
        "recommendations": str_list(raw.get("recommendations")),
    }


# ----------------------------- demonstration data -----------------------------
_DEMO_SCENARIOS = [
    {   # mostly compliant
        "safety_score": 88, "overall_status": "Compliant",
        "ppe_detection": {
            "helmet": {"status": "Detected", "confidence": 94},
            "high_visibility_vest": {"status": "Detected", "confidence": 91},
            "steel_toe_boots": {"status": "Detected", "confidence": 72},
            "safety_harness": {"status": "Unclear", "confidence": 40}},
        "hazards": [{"hazard": "Loose materials near walkway", "severity": "Low",
                     "description": "Sample: offcuts stacked close to a pedestrian route.",
                     "corrective_action": "Stack materials in a designated area away from walkways."}],
        "recommendations": ["Maintain current PPE discipline.", "Confirm harness use whenever work exceeds 1.8 m height.",
                            "Keep housekeeping checks in the daily toolbox talk."],
    },
    {   # partial
        "safety_score": 64, "overall_status": "Partial Compliance",
        "ppe_detection": {
            "helmet": {"status": "Detected", "confidence": 90},
            "high_visibility_vest": {"status": "Not Detected", "confidence": 78},
            "steel_toe_boots": {"status": "Unclear", "confidence": 45},
            "safety_harness": {"status": "Not Detected", "confidence": 82}},
        "hazards": [
            {"hazard": "Work at height without fall protection", "severity": "High",
             "description": "Sample: a worker appears to be on an elevated edge without a harness.",
             "corrective_action": "Stop elevated work until a harness and anchor point are in use."},
            {"hazard": "Exposed reinforcement bars", "severity": "Medium",
             "description": "Sample: protruding rebar ends without protective caps.",
             "corrective_action": "Fit rebar caps or bend the ends back."}],
        "recommendations": ["Issue high-visibility vests to all workers.", "Enforce fall protection above 1.8 m.",
                            "Re-brief the crew on PPE rules before the next shift."],
    },
    {   # poor
        "safety_score": 38, "overall_status": "Non-Compliant",
        "ppe_detection": {
            "helmet": {"status": "Not Detected", "confidence": 86},
            "high_visibility_vest": {"status": "Not Detected", "confidence": 80},
            "steel_toe_boots": {"status": "Not Detected", "confidence": 60},
            "safety_harness": {"status": "Not Detected", "confidence": 88}},
        "hazards": [
            {"hazard": "No head protection", "severity": "Critical",
             "description": "Sample: workers without helmets in an active work zone.",
             "corrective_action": "Halt work in the zone until helmets are worn."},
            {"hazard": "Unguarded edge or opening", "severity": "High",
             "description": "Sample: no visible guardrail at an elevated edge.",
             "corrective_action": "Install guardrails and toe boards."},
            {"hazard": "Poor housekeeping", "severity": "Medium",
             "description": "Sample: debris and tools spread across the work area.",
             "corrective_action": "Clear and organise the area; assign a housekeeping owner."}],
        "recommendations": ["Stop work until helmets, vests and harnesses are provided.", "Hold an immediate safety stand-down.",
                            "Escalate to the site safety officer for a full audit."],
    },
]


def demo_safety_result(seed: Optional[str] = None) -> Dict[str, Any]:
    index = int(seed[:8], 16) % len(_DEMO_SCENARIOS) if seed else 1
    return validate_safety_result(_DEMO_SCENARIOS[index])


def analyze_site_image(service: Optional[GeminiService], image: Any,
                       image_hash: Optional[str] = None) -> Tuple[Dict[str, Any], str, Optional[str]]:
    """Returns (result, mode, notice). Never raises."""
    return run_analysis(
        service, PROMPT, image, validate_safety_result,
        required_keys=("safety_score", "ppe_detection", "hazards"),
        demo_factory=lambda: demo_safety_result(image_hash),
    )
