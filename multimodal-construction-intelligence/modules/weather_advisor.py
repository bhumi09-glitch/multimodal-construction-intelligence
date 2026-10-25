"""EPIC 5 - Weather-aware construction safety advisories (deterministic, no API needed)."""
from __future__ import annotations

from typing import Any, Dict

CONDITIONS = ["Normal", "High Wind", "Heavy Rain", "Extreme Heat"]
DISCLAIMER = ("General guidance only. Follow your site safety plan, equipment manuals, local regulations "
              "and the instructions of the competent safety officer.")

_ADVISORIES: Dict[str, Dict[str, Any]] = {
    "Normal": {
        "risk_level": "Low",
        "summary": "Standard conditions. Maintain routine safety discipline.",
        "alerts": ["No weather-related restrictions in effect.", "Housekeeping and PPE compliance remain the main daily risks."],
        "actions": ["Hold the daily toolbox talk before work starts.", "Inspect scaffolds, ladders and lifting gear.",
                    "Check that barricades and signage are in place.", "Confirm emergency contacts and first-aid kit location."],
        "prohibited": ["Work at height without fall protection", "Entering excavations without inspection and shoring"],
    },
    "High Wind": {
        "risk_level": "High",
        "summary": "Wind raises the risk of falling objects, load swing and loss of balance at height.",
        "alerts": ["Suspend crane lifts when wind exceeds the limit in the manufacturer's manual.",
                   "Loose sheets, formwork and tools can become projectiles.",
                   "Elevated workers face a higher risk of falls."],
        "actions": ["Check wind speed readings at the start of shift and during the day.",
                    "Secure or remove loose materials, sheeting, formwork and tools.",
                    "Lower or lock crane booms and secure tag lines; use taglines on all loads.",
                    "Stop work on scaffolds and roofs when gusts make footing unsafe.",
                    "Keep people clear of the area below elevated work."],
        "prohibited": ["Crane lifts above the permitted wind speed", "Handling large sheets or panels in open areas",
                       "Working on unsecured scaffolds, roof edges or tall masts"],
    },
    "Heavy Rain": {
        "risk_level": "High",
        "summary": "Rain increases electrical, slip, excavation-collapse and concrete-quality risks.",
        "alerts": ["Wet conditions raise electrocution risk from temporary power and tools.",
                   "Excavations and trenches can collapse or flood.",
                   "Surfaces, ladders and scaffold boards become slippery."],
        "actions": ["Isolate and inspect temporary electrical supplies; use RCCB/GFCI protection and keep joints off the ground.",
                    "Inspect excavations and shoring before re-entry; pump out water and keep spoil away from edges.",
                    "Postpone concrete pours or cover fresh concrete; protect it from washout and extra water.",
                    "Cover cement and keep reinforcement and materials off wet ground.",
                    "Clear drains and check that the site slopes water away from structures."],
        "prohibited": ["Using damaged or unprotected electrical equipment", "Entering flooded or unsupported excavations",
                       "Pouring concrete in heavy rain without protection", "Working on wet scaffolds or roofs"],
    },
    "Extreme Heat": {
        "risk_level": "High",
        "summary": "Heat exposure can cause heat exhaustion and heat stroke, and can harm fresh concrete.",
        "alerts": ["Risk of heat exhaustion and heat stroke, especially for new or unacclimatised workers.",
                   "Fresh concrete can lose moisture too quickly and crack.",
                   "Metal tools, scaffolds and formwork can burn skin."],
        "actions": ["Provide shaded rest areas and cool drinking water; encourage regular sips (about a cup every 15-20 minutes).",
                    "Schedule heavy work for early morning and late afternoon; use work/rest cycles in peak heat.",
                    "Watch for dizziness, confusion, cramps or hot dry skin and act on the first signs.",
                    "Start curing early: cover with wet hessian or curing compound and keep the surface moist.",
                    "Consider pouring concrete in the early morning or at night, with cooled materials where needed."],
        "prohibited": ["Heavy exertion during the hottest hours without breaks", "Working alone without a check-in",
                       "Leaving fresh concrete uncured in direct sun"],
    },
}

_BASE_CHECKLIST = ["PPE worn correctly by everyone (helmet, vest, boots, gloves, harness where needed)",
                   "Scaffolds, ladders and edge protection inspected", "Lifting equipment and slings inspected",
                   "Temporary electrics checked and protected", "Emergency contacts, first aid and assembly point confirmed"]
_EXTRA_CHECKLIST = {
    "Normal": ["Toolbox talk completed and attendance recorded"],
    "High Wind": ["Wind speed checked and recorded", "Loose materials secured", "Crane wind-limit rule briefed to operators"],
    "Heavy Rain": ["Drainage and pumps working", "Excavations inspected after rain", "Fresh concrete covered or pour postponed"],
    "Extreme Heat": ["Water and shade available", "Work/rest schedule briefed", "Curing plan active for fresh concrete"],
}


def get_advisory(condition: str) -> Dict[str, Any]:
    """Return the advisory for a condition (falls back to Normal for unknown input)."""
    if condition not in _ADVISORIES:
        condition = "Normal"
    data = _ADVISORIES[condition]
    return {
        "condition": condition,
        "risk_level": data["risk_level"],
        "summary": data["summary"],
        "safety_alerts": list(data["alerts"]),
        "recommended_actions": list(data["actions"]),
        "prohibited_activities": list(data["prohibited"]),
        "daily_checklist": _EXTRA_CHECKLIST[condition] + _BASE_CHECKLIST,
    }
