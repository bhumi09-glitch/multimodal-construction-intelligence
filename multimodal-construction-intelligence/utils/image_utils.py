"""Image upload validation shared by the vision tabs."""
from __future__ import annotations

import hashlib
import io
from typing import Optional, Tuple

from PIL import Image, UnidentifiedImageError

ALLOWED_EXTENSIONS = ("jpg", "jpeg", "png")
MAX_BYTES = 10 * 1024 * 1024
MAX_SIDE = 1600  # downscale large photos to keep API calls fast


def load_uploaded_image(uploaded) -> Tuple[Optional[Image.Image], Optional[str], Optional[str]]:
    """Validate a Streamlit UploadedFile.

    Returns (image, error_message, content_hash). Exactly one of image/error is set.
    """
    if uploaded is None:
        return None, "No file uploaded. Choose a JPG, JPEG or PNG image.", None
    name = (getattr(uploaded, "name", "") or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        return None, f"Unsupported file type '.{ext or '?'}'. Please upload a JPG, JPEG or PNG image.", None
    try:
        data = uploaded.getvalue()
    except Exception:
        return None, "The file could not be read. Please upload it again.", None
    if not data:
        return None, "The uploaded file is empty.", None
    if len(data) > MAX_BYTES:
        return None, "The image is larger than 10 MB. Please upload a smaller file.", None
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()  # detects truncated / corrupt files
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        return None, "This file is not a valid image or is corrupted. Try another photo.", None
    if min(image.size) < 32:
        return None, "The image is too small to analyse (minimum 32 px on each side).", None
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    return image, None, hashlib.md5(data).hexdigest()
