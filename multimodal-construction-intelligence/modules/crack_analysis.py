"""EPIC 2 - Crack diagnostics & structural integrity: prompt, contract, validation, demo data."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from modules.gemini_service import GeminiService, run_analysis
from utils.json_utils import choice, clamp_number, str_list

DEFECT_TYPES = ["Hairline", "Settlement", "Structural Shear", "Thermal Expansion", "Spalling"]
SEVERITIES = ["Low", "Medium", "High", "Critical"]
URGENCIES = ["Routine Monitoring", "Schedule Repair", "Urgent", "Immediate"]
DISCLAIMER = (
    "This is an initial AI-assisted visual assessment. It is not a substitute for an inspection by a "
    "qualified structural engineer. Crack width is a visual estimate without a scale reference."
)

PROMPT = """You are an assistant to a structural engineer. Examine this photo of a concrete surface,
wall or structural element for visible defects. Context: IS 456 (plain and reinforced concrete) and
common Indian repair practice (epoxy injection, structural re-grouting, polymer-modified mortar).

Rules:
- Report only visible evidence. If no defect is visible, use "Hairline" with severity "Low" and say so.
- defect_type must be one of: "Hairline", "Settlement", "Structural Shear", "Thermal Expansion", "Spalling".
- severity is one of "Low", "Medium", "High", "Critical".
- urgency is one of "Routine Monitoring", "Schedule Repair", "Urgent", "Immediate".
- estimated_crack_width_mm is a rough number in millimetres; confidence is 0-100.

Return ONLY valid JSON, no markdown, in exactly this structure:
{"defect_type": "", "severity": "", "estimated_crack_width_mm": 0,
 "visual_observations": [], "possible_root_causes": [], "recommended_repairs": [],
 "urgency": "", "confidence": 0}"""


def validate_crack_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "defect_type": choice(raw.get("defect_type"), DEFECT_TYPES, "Hairline"),
        "severity": choice(raw.get("severity"), SEVERITIES, "Medium"),
        "estimated_crack_width_mm": round(clamp_number(raw.get("estimated_crack_width_mm"), 0, 200, 0), 2),
        "visual_observations": str_list(raw.get("visual_observations")),
        "possible_root_causes": str_list(raw.get("possible_root_causes")),
        "recommended_repairs": str_list(raw.get("recommended_repairs")),
        "urgency": choice(raw.get("urgency"), URGENCIES, "Schedule Repair"),
        "confidence": round(clamp_number(raw.get("confidence"), 0, 100, 0)),
    }


_DEMO_SCENARIOS = [
    {"defect_type": "Hairline", "severity": "Low", "estimated_crack_width_mm": 0.2,
     "visual_observations": ["Sample: fine surface cracks in a map-like pattern", "No displacement across the crack"],
     "possible_root_causes": ["Plastic shrinkage during early curing", "Insufficient curing in hot weather"],
     "recommended_repairs": ["Seal with a flexible crack filler or cement slurry", "Improve curing practice on future pours"],
     "urgency": "Routine Monitoring", "confidence": 78},
    {"defect_type": "Settlement", "severity": "Medium", "estimated_crack_width_mm": 3.5,
     "visual_observations": ["Sample: diagonal stair-step crack in masonry", "Crack is wider at the top than the bottom"],
     "possible_root_causes": ["Differential foundation settlement", "Poor soil compaction or drainage near the footing"],
     "recommended_repairs": ["Investigate the foundation and drainage", "Epoxy injection once movement has stabilised",
                             "Install crack gauges to monitor movement"],
     "urgency": "Schedule Repair", "confidence": 72},
    {"defect_type": "Structural Shear", "severity": "High", "estimated_crack_width_mm": 6.0,
     "visual_observations": ["Sample: 45-degree diagonal crack near a beam support", "Crack extends through the section depth"],
     "possible_root_causes": ["Insufficient shear reinforcement or overload", "Reduced bearing at the support"],
     "recommended_repairs": ["Restrict loading and call a structural engineer immediately", "Structural re-grouting and epoxy injection",
                             "Consider jacketing or external strengthening after engineering design"],
     "urgency": "Immediate", "confidence": 69},
    {"defect_type": "Thermal Expansion", "severity": "Low", "estimated_crack_width_mm": 1.2,
     "visual_observations": ["Sample: straight cracks at regular intervals on an exposed slab", "Cracks align with changes in section"],
     "possible_root_causes": ["Missing or inadequate expansion joints", "Large daily temperature swings"],
     "recommended_repairs": ["Cut and seal expansion joints with polyurethane sealant", "Apply reflective coating on exposed surfaces"],
     "urgency": "Routine Monitoring", "confidence": 74},
    {"defect_type": "Spalling", "severity": "Medium", "estimated_crack_width_mm": 2.0,
     "visual_observations": ["Sample: concrete cover has flaked off exposing rusted rebar", "Rust staining around the damaged area"],
     "possible_root_causes": ["Reinforcement corrosion from moisture or chloride ingress", "Inadequate concrete cover"],
     "recommended_repairs": ["Remove loose concrete and clean the rebar", "Apply anti-corrosion primer and polymer-modified repair mortar",
                             "Apply a protective waterproof coating"],
     "urgency": "Urgent", "confidence": 76},
]


def demo_crack_result(seed: Optional[str] = None) -> Dict[str, Any]:
    index = int(seed[:8], 16) % len(_DEMO_SCENARIOS) if seed else 1
    return validate_crack_result(_DEMO_SCENARIOS[index])


def analyze_crack_image(service: Optional[GeminiService], image: Any,
                        image_hash: Optional[str] = None) -> Tuple[Dict[str, Any], str, Optional[str]]:
    return run_analysis(
        service, PROMPT, image, validate_crack_result,
        required_keys=("defect_type", "severity", "visual_observations"),
        demo_factory=lambda: demo_crack_result(image_hash),
    )
