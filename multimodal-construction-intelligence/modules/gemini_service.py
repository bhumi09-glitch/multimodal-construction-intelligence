"""Gemini wrapper (EPIC 4 - Multimodal AI).

* Never raises raw SDK errors to the UI: everything becomes GeminiServiceError
  with a message that is safe to show to end users.
* `run_analysis` is the single place where "live AI -> parse -> validate ->
  fall back to demo data" is implemented, so every module behaves identically.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from utils.json_utils import extract_json

logger = logging.getLogger(__name__)
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


class GeminiServiceError(Exception):
    """An error whose message is safe to display to normal users."""


def _friendly_message(exc: Exception) -> str:
    msg = f"{type(exc).__name__} {exc}".lower()
    if any(k in msg for k in ("api key not valid", "api_key_invalid", "permission_denied", "401", "403", "unauthenticated")):
        return "The Gemini API key was rejected. Check that the key is correct and enabled."
    if any(k in msg for k in ("429", "quota", "resource_exhausted", "rate limit")):
        return "Gemini rate limit or quota reached. Wait a minute and try again."
    if any(k in msg for k in ("timeout", "timed out", "deadline")):
        return "The request to Gemini timed out. Please try again."
    if any(k in msg for k in ("connect", "network", "dns", "unreachable", "ssl", "name resolution", "temporary failure")):
        return "Could not reach the Gemini service. Check your internet connection."
    if any(k in msg for k in ("safety", "blocked")):
        return "Gemini declined to process this content. Try a different image or question."
    return "Gemini could not complete the request."


class GeminiService:
    """Thin client around the google-genai SDK."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        from google import genai  # imported lazily so the app still runs without the SDK
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60_000))
        self.model = model

    @classmethod
    def create(cls, api_key: Optional[str]) -> Tuple[Optional["GeminiService"], Optional[str]]:
        """Return (service, error). A blank key is not an error: it means demo mode."""
        key = (api_key or "").strip()
        if not key:
            return None, None
        try:
            return cls(key), None
        except ImportError:
            return None, "The 'google-genai' package is not installed, so the app stays in Demo Mode."
        except Exception:
            logger.exception("Gemini client initialisation failed")
            return None, "Could not initialise the Gemini client. Check the API key format."

    def generate(self, prompt: str, image: Any = None, json_mode: bool = False,
                 system_instruction: Optional[str] = None) -> str:
        config = self._types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json" if json_mode else None,
            system_instruction=system_instruction,
        )
        contents = [image, prompt] if image is not None else prompt
        try:
            response = self._client.models.generate_content(model=self.model, contents=contents, config=config)
            output = getattr(response, "text", None)
        except Exception as exc:  # SDK/network errors
            logger.warning("Gemini call failed: %s", type(exc).__name__)
            raise GeminiServiceError(_friendly_message(exc)) from exc
        if not output or not output.strip():
            raise GeminiServiceError("Gemini returned an empty response.")
        return output


def run_analysis(
    service: Optional[GeminiService],
    prompt: str,
    image: Any,
    validate: Callable[[Dict[str, Any]], Dict[str, Any]],
    required_keys: Iterable[str],
    demo_factory: Callable[[], Dict[str, Any]],
) -> Tuple[Dict[str, Any], str, Optional[str]]:
    """Return (result_dict, mode, notice). mode is 'live' or 'demo'. Never raises."""
    if service is None:
        return demo_factory(), "demo", None
    try:
        raw_text = service.generate(prompt, image=image, json_mode=True)
        data = extract_json(raw_text)
        if not data or not any(k in data for k in required_keys):
            raise GeminiServiceError("Gemini returned a response that could not be read as the expected JSON.")
        return validate(data), "live", None
    except GeminiServiceError as exc:
        return demo_factory(), "demo", f"{exc} Showing demonstration data instead."
    except Exception:
        logger.exception("Unexpected analysis failure")
        return demo_factory(), "demo", "An unexpected problem occurred. Showing demonstration data instead."
