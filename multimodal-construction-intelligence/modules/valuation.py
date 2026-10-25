"""EPIC 3 - Project planning, real-estate valuation and architectural prompt generator.

All figures are CONCEPTUAL, rule-of-thumb estimates in INR. They are not quotations,
valuations by a certified valuer, or guaranteed market prices.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DISCLAIMER = (
    "Conceptual, approximate estimates based on simple rule-of-thumb rates. They are not guaranteed market "
    "prices, a bill of quantities, or a certified valuation. Get quotes and a registered valuer for decisions."
)

STRUCTURE_TYPES = ["Residential", "Commercial", "Industrial", "Other"]
LOCATION_TIERS = ["Tier 1", "Tier 2", "Tier 3"]
QUALITY_LEVELS = ["Basic", "Standard", "Premium"]

# base construction cost INR/sq ft, steel kg/sq ft, cement bags (50 kg)/sq ft
_RATES = {
    "Residential": {"cost": 1900, "steel": 4.0, "cement": 0.40},
    "Commercial": {"cost": 2600, "steel": 5.0, "cement": 0.45},
    "Industrial": {"cost": 1700, "steel": 6.0, "cement": 0.50},
    "Other": {"cost": 2100, "steel": 4.5, "cement": 0.42},
}
_TIER_COST = {"Tier 1": 1.25, "Tier 2": 1.0, "Tier 3": 0.85}      # construction cost multiplier
_TIER_MARKET = {"Tier 1": 2.4, "Tier 2": 1.7, "Tier 3": 1.25}     # market value / cost ratio
_QUALITY = {"Basic": 0.85, "Standard": 1.0, "Premium": 1.35}
_BREAKDOWN = [("Foundation & structure", 0.38), ("Masonry & finishing", 0.27),
              ("Electrical, plumbing & MEP", 0.20), ("External works & misc.", 0.15)]
MILESTONES = [("Site preparation & foundation", 0, 15), ("Structural frame", 15, 45),
              ("Masonry & roofing", 45, 60), ("MEP services", 60, 75),
              ("Finishing & fit-out", 75, 95), ("Handover & snagging", 95, 100)]

MAX_AREA = 10_000_000


def format_inr(amount: float) -> str:
    """Format INR using Crore / Lakh units, e.g. 'Rs 1.25 Crore'."""
    amount = float(amount)
    sign = "-" if amount < 0 else ""
    value = abs(amount)
    if value >= 1e7:
        return f"{sign}\u20b9{value / 1e7:,.2f} Crore"
    if value >= 1e5:
        return f"{sign}\u20b9{value / 1e5:,.2f} Lakh"
    return f"{sign}\u20b9{value:,.0f}"


def compute_valuation(structure_type: str, area_sqft: float, location_tier: str,
                      completion_pct: float, quality: str = "Standard",
                      land_value_lakh: float = 0.0) -> Dict[str, Any]:
    """Validate inputs and return the planning/valuation estimate. Raises ValueError on bad input."""
    if structure_type not in _RATES:
        raise ValueError("Unknown structure type.")
    if location_tier not in _TIER_COST:
        raise ValueError("Unknown location tier.")
    if quality not in _QUALITY:
        raise ValueError("Unknown quality level.")
    try:
        area, pct, land = float(area_sqft), float(completion_pct), float(land_value_lakh)
    except (TypeError, ValueError):
        raise ValueError("Area, completion and land value must be numbers.")
    if not (area > 0) or area > MAX_AREA:
        raise ValueError(f"Built-up area must be greater than 0 and at most {MAX_AREA:,} sq ft.")
    if not (0 <= pct <= 100):
        raise ValueError("Completion must be between 0 and 100 percent.")
    if land < 0:
        raise ValueError("Land value cannot be negative.")

    rate = _RATES[structure_type]
    cost_per_sqft = rate["cost"] * _TIER_COST[location_tier] * _QUALITY[quality]
    total_budget = area * cost_per_sqft
    fraction = pct / 100
    land_inr = land * 1e5
    building_market_value = total_budget * _TIER_MARKET[location_tier]
    steel_t = area * rate["steel"] / 1000
    cement_bags = area * rate["cement"]
    return {
        "inputs": {"structure_type": structure_type, "built_up_area_sqft": area, "location_tier": location_tier,
                   "completion_percent": pct, "quality": quality, "land_value_inr": land_inr},
        "cost_per_sqft_inr": round(cost_per_sqft),
        "total_project_budget_inr": round(total_budget),
        "capital_expenditure_incurred_inr": round(total_budget * fraction),
        "remaining_budget_inr": round(total_budget * (1 - fraction)),
        "market_value_at_completion_inr": round(building_market_value + land_inr),
        "current_market_asset_valuation_inr": round(building_market_value * fraction + land_inr),
        "steel_requirement_tonnes": round(steel_t, 2),
        "cement_requirement_bags": round(cement_bags),
        "cement_requirement_tonnes": round(cement_bags * 50 / 1000, 2),
        "steel_consumed_tonnes": round(steel_t * fraction, 2),
        "cement_consumed_bags": round(cement_bags * fraction),
        "cost_breakdown_inr": {name: round(total_budget * share) for name, share in _BREAKDOWN},
        "milestones": milestone_status(pct),
        "estimate_notice": "Conceptual / approximate estimate - not a guaranteed market price.",
    }


def milestone_status(completion_pct: float) -> List[Dict[str, Any]]:
    rows = []
    for name, start, end in MILESTONES:
        progress = max(0.0, min(1.0, (completion_pct - start) / (end - start)))
        state = "Complete" if progress >= 1 else ("In progress" if progress > 0 else "Not started")
        rows.append({"milestone": name, "range_percent": f"{start}-{end}%", "progress": round(progress, 3), "state": state})
    return rows


def build_architectural_prompt(structure_type: str, area_sqft: float, location_tier: str,
                               completion_pct: float, description: Optional[str] = None) -> str:
    """Create a detailed text-to-image prompt. No external image API is required or called."""
    scale = ("compact" if area_sqft < 1500 else "mid-sized" if area_sqft < 5000
             else "large" if area_sqft < 25000 else "very large, multi-block")
    setting = {"Tier 1": "dense metropolitan streetscape with surrounding high-rise context",
               "Tier 2": "growing city neighbourhood with mixed low and mid-rise buildings",
               "Tier 3": "town or semi-urban setting with open surroundings and mature trees"}[location_tier]
    style = {"Residential": "contemporary Indian residential design with balconies, jali screens and landscaped entry",
             "Commercial": "modern commercial building with glazed facade, covered entrance and signage zone",
             "Industrial": "functional industrial facility with clear-span roof, loading bays and steel cladding",
             "Other": "contemporary institutional-style building with clean massing and public entrance"}[structure_type]
    if completion_pct < 15:
        stage = "early site stage: excavation, footings and rebar visible, tower crane and barricades"
    elif completion_pct < 60:
        stage = "structure under construction: exposed RCC frame, scaffolding, partial brick infill, workers in PPE"
    elif completion_pct < 95:
        stage = "late construction: facade partially clad, plastering and window installation underway"
    else:
        stage = "completed building: finished facade, landscaping, clean paved access, warm evening light"
    extra = f" Additional client notes: {description.strip()[:400]}." if description and description.strip() else ""
    return (f"Architectural visualization, photorealistic, of a {scale} {structure_type.lower()} building "
            f"(about {int(area_sqft):,} sq ft built-up) in a {setting}. Design language: {style}. "
            f"Depicted at {int(completion_pct)}% completion - {stage}. Camera: eye-level three-quarter view, "
            f"wide-angle lens, soft natural daylight, realistic materials (concrete, brick, glass, steel), "
            f"high detail, 16:9.{extra} Conceptual render for planning discussion only.")
