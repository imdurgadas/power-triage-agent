import os
import base64
import logging
from typing import Optional, List
from google.genai import types

logger = logging.getLogger("gemini_helper")


def get_candidate_models() -> List[str]:
    primary = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip()
    fallbacks = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash-lite"]
    models = []
    for m in [primary] + fallbacks:
        if m and m not in models:
            models.append(m)
    return models


def generate_gemini_content(
    client,
    contents: str,
    json_mode: bool = False,
    image_data_base64: Optional[str] = None,
    image_media_type: str = "image/png",
) -> Optional[str]:
    """Generates content using Gemini with automatic rate-limit (429) fallback across candidate models.

    When ``image_data_base64`` is supplied, the prompt is sent as a multipart
    vision request: the image is prepended as an inline_data part so Gemini can
    read text/diagrams visible in the screenshot before processing the manifest.
    """
    if not client:
        return None

    candidate_models = get_candidate_models()
    config = types.GenerateContentConfig(
        response_mime_type="application/json"
    ) if json_mode else None

    # Build the contents list — always include the text prompt; optionally
    # prepend an image part for vision models.
    if image_data_base64:
        try:
            raw_bytes = base64.b64decode(image_data_base64)
            contents_payload = [
                types.Part(
                    inline_data=types.Blob(
                        mime_type=image_media_type,
                        data=raw_bytes,
                    )
                ),
                types.Part(text=contents),
            ]
        except Exception as exc:
            logger.warning("Failed to decode image_data_base64, falling back to text-only: %s", exc)
            contents_payload = contents
    else:
        contents_payload = contents

    last_error = None
    for model_name in candidate_models:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=contents_payload,
                config=config
            )
            if resp and resp.text:
                return resp.text.strip()
        except Exception as e:
            err_str = str(e)
            last_error = e
            # If rate-limited (429 / RESOURCE_EXHAUSTED), unavailable (503), or not found (404), fall back
            if any(code in err_str for code in ["429", "RESOURCE_EXHAUSTED", "503", "404"]):
                logger.warning(f"Gemini model '{model_name}' hit rate limit/unavailable ({err_str[:90]}...). Trying fallback model...")
                continue
            else:
                logger.error(f"Gemini call error on model '{model_name}': {e}")
                break

    if last_error:
        logger.warning(f"All candidate Gemini models failed. Last error: {last_error}")
    return None
