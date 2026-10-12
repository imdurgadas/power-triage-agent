import os
import base64
import logging
from typing import Optional, List, Tuple
from google.genai import types

logger = logging.getLogger("gemini_helper")


# In-memory prompt cache to speed up repeated queries and avoid re-triggering API quotas
_GEMINI_PROMPT_CACHE = {}


def get_candidate_models() -> List[str]:
    primary = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    fallbacks = ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash", "gemini-2.5-flash-lite"]
    models = []
    for m in [primary] + fallbacks:
        if m and m not in models:
            models.append(m)
    return models


def generate_gemini_content_with_usage(
    client,
    contents: str,
    json_mode: bool = False,
    image_data_base64: Optional[str] = None,
    image_media_type: str = "image/png",
    timeout_ms: int = 15000,
) -> Tuple[Optional[str], int, int, float]:
    """Generates content using Gemini, capturing prompt tokens, candidate tokens, and cost.

    Returns:
        (text, input_tokens, output_tokens, cost_usd)
    """
    if not client:
        return None, 0, 0, 0.0

    cache_key = None
    if not image_data_base64 and isinstance(contents, str):
        cache_key = f"{json_mode}::{contents}"
        if cache_key in _GEMINI_PROMPT_CACHE:
            cached_text = _GEMINI_PROMPT_CACHE[cache_key]
            in_tok = max(1, len(contents) // 4)
            out_tok = max(1, len(cached_text) // 4)
            return cached_text, in_tok, out_tok, (in_tok * 0.000000075 + out_tok * 0.00000030)

    candidate_models = get_candidate_models()
    http_opts = types.HttpOptions(timeout=timeout_ms)
    config = types.GenerateContentConfig(
        response_mime_type="application/json" if json_mode else None,
        http_options=http_opts,
    )

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
                result = resp.text.strip()
                if cache_key:
                    _GEMINI_PROMPT_CACHE[cache_key] = result

                input_tokens = 0
                output_tokens = 0
                if getattr(resp, "usage_metadata", None):
                    input_tokens = int(getattr(resp.usage_metadata, "prompt_token_count", 0) or 0)
                    output_tokens = int(getattr(resp.usage_metadata, "candidates_token_count", 0) or 0)

                if input_tokens == 0:
                    input_tokens = max(1, len(contents) // 4)
                if output_tokens == 0:
                    output_tokens = max(1, len(result) // 4)

                cost_usd = round((input_tokens * 0.000000075) + (output_tokens * 0.00000030), 6)
                return result, input_tokens, output_tokens, cost_usd
        except Exception as e:
            err_str = str(e)
            last_error = e
            if any(code in err_str.lower() for code in ["429", "resource_exhausted", "503", "404", "timeout", "timed out", "deadline"]):
                logger.warning(f"Gemini model '{model_name}' hit rate limit/unavailable ({err_str[:90]}...). Trying fallback model...")
                continue
            else:
                logger.error(f"Gemini call error on model '{model_name}': {e}")
                break

    if last_error:
        logger.warning(f"All candidate Gemini models failed. Last error: {last_error}")
    return None, 0, 0, 0.0


def generate_gemini_content(
    client,
    contents: str,
    json_mode: bool = False,
    image_data_base64: Optional[str] = None,
    image_media_type: str = "image/png",
    timeout_ms: int = 15000,
) -> Optional[str]:
    """Generates content using Gemini with backwards-compatible return signature."""
    text, _, _, _ = generate_gemini_content_with_usage(
        client=client,
        contents=contents,
        json_mode=json_mode,
        image_data_base64=image_data_base64,
        image_media_type=image_media_type,
        timeout_ms=timeout_ms,
    )
    return text

