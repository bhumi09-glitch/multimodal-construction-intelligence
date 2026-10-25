"""EPIC 5 - Construction engineering chatbot (Gemini when available, deterministic demo otherwise)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from modules.gemini_service import GeminiService, GeminiServiceError

logger = logging.getLogger(__name__)
MAX_QUESTION_CHARS = 1000

SYSTEM_PROMPT = (
    "You are a construction site assistant for civil engineering students and site supervisors in India. "
    "Answer practical construction, site-safety, concrete, materials and defect questions clearly and concisely "
    "(under 220 words, short bullet points where useful). Reference OSHA 29 CFR 1926 or IS 456 only when relevant. "
    "Do not invent specific code clause numbers. For structural safety concerns, advise consulting a qualified "
    "structural engineer. If a question is outside construction, politely say so."
)

EXAMPLE_QUESTIONS = ["What precautions should I take during heavy rain?",
                     "What should I check before concrete pouring?",
                     "Why are cracks appearing on this wall?"]

# (keywords, answer) - first match with the most keyword hits wins
_KNOWLEDGE_BASE: List[Tuple[Tuple[str, ...], str]] = [
    (("rain", "monsoon", "wet", "flood"),
     "**Heavy rain precautions**\n- Isolate temporary power, use RCCB protection and keep joints off the ground.\n"
     "- Inspect excavations and shoring before re-entry; pump out water and keep spoil away from edges.\n"
     "- Postpone concrete pours or cover fresh concrete to prevent washout.\n- Keep cement dry and materials off wet ground.\n"
     "- Treat scaffolds and ladders as slippery; stop elevated work if unsafe."),
    (("pour", "pouring", "concreting", "before concrete", "casting"),
     "**Pre-pour checklist**\n- Formwork is clean, tight, aligned and properly propped.\n- Reinforcement matches drawings, with correct cover blocks and laps.\n"
     "- Embedded items (conduits, sleeves) are fixed and approved.\n- Mix design, slump test and cube-casting arrangements are ready.\n"
     "- Enough labour, vibrators and a curing plan are in place; check the weather forecast.\n- Get written approval from the engineer before pouring."),
    (("crack", "cracks", "wall crack", "cracking"),
     "**Why walls crack (common causes)**\n- Plastic shrinkage or poor curing: fine, early surface cracks.\n"
     "- Foundation settlement: diagonal or stair-step cracks wider at one end.\n- Thermal movement: straight cracks at regular spacing.\n"
     "- Overload or shear: diagonal cracks near supports (serious).\n- Corrosion of reinforcement: cracks and spalling with rust stains.\n"
     "Measure the width, monitor with tell-tales, and call a structural engineer for wide, growing or diagonal cracks. "
     "You can also use the Crack Diagnostics module for an initial assessment."),
    (("wind", "storm", "crane", "gust"),
     "**High wind precautions**\n- Stop crane lifts above the manufacturer's wind limit.\n- Secure loose materials, sheets and formwork.\n"
     "- Suspend work at height when footing is unsafe.\n- Use taglines on loads and keep people out of the drop zone."),
    (("heat", "hot", "summer", "hydration", "sun"),
     "**Extreme heat precautions**\n- Provide shade and cool water; plan regular rest breaks.\n- Move heavy work to cooler hours.\n"
     "- Watch for heat illness signs: dizziness, cramps, confusion, hot dry skin.\n- Start curing concrete early and keep it moist."),
    (("curing", "cure"),
     "**Curing basics**\n- Begin curing as soon as the surface can take it without damage.\n- Keep concrete continuously moist (ponding, wet hessian or curing compound).\n"
     "- Ordinary Portland cement concrete is commonly cured for at least 7 days, longer for blended cements or hot weather; confirm with your project specification."),
    (("ppe", "helmet", "harness", "vest", "boots", "protective"),
     "**Core PPE**\n- Safety helmet: always in work zones.\n- High-visibility vest: near traffic and machinery.\n- Safety footwear with toe protection.\n"
     "- Full-body harness with anchorage for work at height.\n- Add gloves, eye and hearing protection by task. PPE is the last line of defence after hazard control."),
    (("scaffold", "height", "fall", "ladder"),
     "**Work at height**\n- Use properly erected, inspected scaffolds with guardrails, toe boards and safe access.\n- Use a harness when other fall protection is not in place.\n"
     "- Never overload platforms or climb braces.\n- Inspect before each shift and after weather events."),
    (("excavation", "trench", "shoring"),
     "**Excavation safety**\n- Inspect daily and after rain; provide shoring or sloping for deep trenches.\n- Keep spoil and equipment back from the edge.\n"
     "- Provide ladders for entry and exit; never work alone; check for utilities before digging."),
    (("cement", "steel", "quantity", "estimate"),
     "**Rough material rules of thumb**\n- Residential buildings often need roughly 0.4 bags of cement and 3.5-4.5 kg of steel per sq ft of built-up area.\n"
     "- Use the Planning & Valuation module for a conceptual estimate, and a quantity surveyor for a real BOQ."),
]


def demo_answer(question: str, context: Optional[Dict[str, Any]] = None) -> str:
    """Deterministic keyword-based answer used in Demo Mode or on API failure."""
    q = question.lower()
    best, hits = None, 0
    for keywords, answer in _KNOWLEDGE_BASE:
        score = sum(1 for k in keywords if k in q)
        if score > hits:
            best, hits = answer, score
    if best is None:
        best = ("I can help with site safety, weather precautions, concrete work, PPE, scaffolding, excavation, "
                "cracks and material estimates. Try asking, for example: 'What should I check before concrete pouring?'")
    extras = []
    ctx = context or {}
    if ctx.get("crack") and any(w in q for w in ("crack", "wall")):
        extras.append(f"Your latest crack analysis classified the defect as **{ctx['crack']['defect_type']}** "
                      f"({ctx['crack']['severity']} severity).")
    if ctx.get("weather") and ctx["weather"] != "Normal" and any(w in q for w in ("today", "site", "now")):
        extras.append(f"Today's selected weather condition is **{ctx['weather']}**; see the Weather Advisory tab.")
    return best + ("\n\n" + " ".join(extras) if extras else "")


def answer_question(service: Optional[GeminiService], question: str, history: List[Dict[str, str]],
                    context: Optional[Dict[str, Any]] = None) -> Tuple[str, str, Optional[str]]:
    """Return (reply, mode, notice). Never raises."""
    question = (question or "").strip()[:MAX_QUESTION_CHARS]
    if not question:
        return "Please type a construction question.", "demo", None
    if service is None:
        return demo_answer(question, context), "demo", None
    ctx = context or {}
    ctx_lines = []
    if ctx.get("weather"):
        ctx_lines.append(f"Selected site weather: {ctx['weather']}")
    if ctx.get("safety"):
        ctx_lines.append(f"Latest PPE audit: score {ctx['safety']['safety_score']}, {ctx['safety']['overall_status']}")
    if ctx.get("crack"):
        ctx_lines.append(f"Latest crack analysis: {ctx['crack']['defect_type']}, {ctx['crack']['severity']} severity")
    recent = "\n".join(f"{m['role'].title()}: {m['content']}" for m in history[-6:])
    prompt = (f"Site context:\n{chr(10).join(ctx_lines) or 'None provided'}\n\nRecent conversation:\n{recent or 'None'}\n\n"
              f"User question: {question}")
    try:
        return service.generate(prompt, system_instruction=SYSTEM_PROMPT), "live", None
    except GeminiServiceError as exc:
        return demo_answer(question, context), "demo", f"{exc} Showing an offline answer instead."
    except Exception:
        logger.exception("Assistant failure")
        return demo_answer(question, context), "demo", "Unexpected problem. Showing an offline answer instead."
