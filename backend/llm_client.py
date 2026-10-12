"""
llm_client.py
Unified LLM Orchestrator supporting IBM Bob and Google Gemini with
fine-grained token usage and cost accounting.
"""

import logging
import os
import shutil
from typing import Any, Dict, Optional, Tuple

from .bob_client import BobClient, BobExecutionResult
from .gemini_helper import generate_gemini_content_with_usage
from .models import TokenUsage, TokenStageBreakdown

logger = logging.getLogger("llm_client")


class TokenTracker:
    """Thread-safe accumulator for LLM input/output tokens, monetary cost, and stage breakdown."""

    def __init__(self, provider: str = "ibm_bob", model: str = "bob-shell"):
        self.provider = provider
        self.model = model
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.cost_usd = 0.0
        self.calls_count = 0
        self.stage_breakdown: Dict[str, Dict[str, Any]] = {}

    def record(self, input_tokens: int, output_tokens: int, cost_usd: float, stage: Optional[str] = None):
        in_tok = int(input_tokens or 0)
        out_tok = int(output_tokens or 0)
        tot_tok = in_tok + out_tok
        cost = float(cost_usd or 0.0)

        self.input_tokens += in_tok
        self.output_tokens += out_tok
        self.total_tokens += tot_tok
        self.cost_usd += cost
        self.calls_count += 1

        stage_name = stage or "General Analysis"
        if stage_name not in self.stage_breakdown:
            self.stage_breakdown[stage_name] = {
                "stage": stage_name,
                "calls_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
            }
        sb = self.stage_breakdown[stage_name]
        sb["calls_count"] += 1
        sb["input_tokens"] += in_tok
        sb["output_tokens"] += out_tok
        sb["total_tokens"] += tot_tok
        sb["cost_usd"] += cost

    def to_model(self) -> TokenUsage:
        breakdown_items = []
        for s_name, s_data in self.stage_breakdown.items():
            if self.cost_usd > 0:
                pct = round((s_data["cost_usd"] / self.cost_usd) * 100, 1)
            elif self.total_tokens > 0:
                pct = round((s_data["total_tokens"] / self.total_tokens) * 100, 1)
            else:
                pct = 0.0
            breakdown_items.append(
                TokenStageBreakdown(
                    stage=s_name,
                    calls_count=s_data["calls_count"],
                    input_tokens=s_data["input_tokens"],
                    output_tokens=s_data["output_tokens"],
                    total_tokens=s_data["total_tokens"],
                    cost_usd=round(s_data["cost_usd"], 6),
                    percentage=pct,
                )
            )
        breakdown_items.sort(key=lambda x: (x.cost_usd, x.total_tokens), reverse=True)

        return TokenUsage(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.total_tokens,
            cost_usd=round(self.cost_usd, 6),
            llm_provider=self.provider,
            llm_model=self.model,
            calls_count=self.calls_count,
            breakdown=breakdown_items,
        )


class LLMService:
    """Multi-provider LLM gateway supporting IBM Bob and Google Gemini."""

    def __init__(
        self,
        provider: Optional[str] = None,
        bobshell_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ):
        self.bobshell_api_key = (
            bobshell_api_key
            or os.environ.get("BOBSHELL_API_KEY", "")
            or os.environ.get("BOB_API_KEY", "")
        )
        self.gemini_api_key = (
            gemini_api_key
            or os.environ.get("GEMINI_API_KEY", "")
        )

        # Initialize IBM Bob Client
        self.bob_client = BobClient(api_key=self.bobshell_api_key)

        # Initialize Gemini Client if key present
        self.gemini_client = None
        if self.gemini_api_key and self.gemini_api_key.strip() and not self.gemini_api_key.startswith("your_"):
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.gemini_api_key.strip())
            except Exception as e:
                logger.warning("Could not initialize Google GenAI Client: %s", e)

        # Resolve active provider
        self.provider = self._resolve_provider(provider)
        model_name = "bob-shell" if self.provider == "ibm_bob" else os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        self.tracker = TokenTracker(provider=self.provider, model=model_name)

        logger.info(
            "LLMService initialized with provider '%s' (Bob available: %s, Gemini available: %s)",
            self.provider, self.bob_client.is_available(), bool(self.gemini_client)
        )

    def _resolve_provider(self, requested: Optional[str]) -> str:
        req = (requested or os.environ.get("LLM_PROVIDER", "")).lower().strip()
        if req in ("ibm_bob", "bob", "bobshell"):
            return "ibm_bob"
        if req in ("gemini", "google_gemini"):
            return "gemini"

        # Auto resolution: prefer IBM Bob if available
        if self.bob_client.is_available():
            return "ibm_bob"
        if self.gemini_client is not None:
            return "gemini"
        return "ibm_bob"

    def is_active(self) -> bool:
        if self.provider == "ibm_bob":
            return self.bob_client.is_available()
        return self.gemini_client is not None

    def get_token_usage(self) -> TokenUsage:
        return self.tracker.to_model()

    def generate_content(
        self,
        contents: str,
        json_mode: bool = False,
        image_data_base64: Optional[str] = None,
        image_media_type: str = "image/png",
        timeout_ms: int = 15000,
        stage: Optional[str] = None,
    ) -> Optional[str]:
        """Routes prompt to the configured LLM provider and records token/cost usage."""
        # 1. Primary: IBM Bob
        if self.provider == "ibm_bob":
            if self.bob_client.is_available():
                res = self.bob_client.generate_content(
                    prompt=contents,
                    json_mode=json_mode,
                    image_data_base64=image_data_base64,
                    image_media_type=image_media_type,
                )
                if res.is_success and res.text:
                    self.tracker.record(res.input_tokens, res.output_tokens, res.cost_usd, stage=stage)
                    return res.text
                else:
                    logger.warning("IBM Bob call failed (%s). Checking Gemini fallback...", res.error)

            # Fallback to Gemini if Bob failed or unavailable
            if self.gemini_client:
                logger.info("Falling back to Gemini for prompt execution...")
                text, in_tok, out_tok, cost = generate_gemini_content_with_usage(
                    self.gemini_client,
                    contents,
                    json_mode=json_mode,
                    image_data_base64=image_data_base64,
                    image_media_type=image_media_type,
                    timeout_ms=timeout_ms,
                )
                if text:
                    self.tracker.record(in_tok, out_tok, cost, stage=stage)
                    return text
            return None

        # 2. Primary: Google Gemini
        if self.gemini_client:
            text, in_tok, out_tok, cost = generate_gemini_content_with_usage(
                self.gemini_client,
                contents,
                json_mode=json_mode,
                image_data_base64=image_data_base64,
                image_media_type=image_media_type,
                timeout_ms=timeout_ms,
            )
            if text:
                self.tracker.record(in_tok, out_tok, cost, stage=stage)
                return text
            logger.warning("Gemini call failed. Checking IBM Bob fallback...")

        # Fallback to Bob if Gemini failed or unavailable
        if self.bob_client.is_available():
            res = self.bob_client.generate_content(
                prompt=contents,
                json_mode=json_mode,
                image_data_base64=image_data_base64,
                image_media_type=image_media_type,
            )
            if res.is_success and res.text:
                self.tracker.record(res.input_tokens, res.output_tokens, res.cost_usd, stage=stage)
                return res.text

        return None
