"""
bob_client.py
Encapsulates interaction with the IBM Bob CLI: headless execution,
structured output extraction, and real-time token/cost telemetry.
Referenced from bob-shell-agents/pr-reviewer.
"""

import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass, field
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bob_client")


@dataclass
class BobExecutionResult:
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    task_id: str = ""
    is_success: bool = True
    error: Optional[str] = None
    json_data: Optional[Dict[str, Any]] = None


class BobClient:
    """Dedicated client to execute and manage IBM Bob headless runs with telemetry."""

    def __init__(
        self,
        api_key: str = "",
        binary: str = "bob",
        timeout: int = 180,
    ):
        self.api_key = api_key or os.environ.get("BOBSHELL_API_KEY", "") or os.environ.get("BOB_API_KEY", "")
        # Resolve binary across PATH and standard container / user paths
        resolved = (
            shutil.which(binary)
            or shutil.which("bob")
            or ("/Users/durgadas/.nvm/versions/node/v24.18.0/bin/bob" if os.path.exists("/Users/durgadas/.nvm/versions/node/v24.18.0/bin/bob") else None)
            or ("/usr/local/bin/bob" if os.path.exists("/usr/local/bin/bob") else None)
            or ("/opt/app-root/bin/bob" if os.path.exists("/opt/app-root/bin/bob") else None)
            or binary
        )
        self.binary = resolved
        self.timeout = timeout

    def is_available(self) -> bool:
        """Returns True if the bob binary is present and an API key is configured."""
        if not self.binary or not shutil.which(self.binary):
            return False
        return bool(self.api_key and self.api_key.strip() and not self.api_key.startswith("your_"))

    def generate_content(
        self,
        prompt: str,
        json_mode: bool = False,
        image_data_base64: Optional[str] = None,
        image_media_type: str = "image/png",
    ) -> BobExecutionResult:
        """Executes IBM Bob in headless mode and extracts response text, tokens, and cost."""
        if not self.is_available():
            err_msg = "IBM Bob is not available (missing binary or BOBSHELL_API_KEY)."
            logger.warning(err_msg)
            return BobExecutionResult(is_success=False, error=err_msg)

        workspace_dir = tempfile.mkdtemp(prefix="bob_analysis_")
        workspace = Path(workspace_dir)
        report_file = workspace / "bob_response.json"

        # If vision input is provided, write image to workspace for Bob
        augmented_prompt = prompt
        if image_data_base64:
            try:
                import base64
                ext = "png"
                if "jpeg" in image_media_type or "jpg" in image_media_type:
                    ext = "jpg"
                elif "webp" in image_media_type:
                    ext = "webp"
                img_path = workspace / f"input_manifest_diagram.{ext}"
                img_path.write_bytes(base64.b64decode(image_data_base64))
                augmented_prompt = (
                    f"A software dependency image or architecture diagram was saved to '{img_path.name}'. "
                    f"Inspect this image file if needed.\n\n"
                    f"{augmented_prompt}"
                )
            except Exception as e:
                logger.warning("Could not persist image to workspace for Bob: %s", e)

        if json_mode:
            augmented_prompt = (
                f"{augmented_prompt}\n\n"
                "IMPORTANT: In addition to outputting your answer, write your final structured JSON response "
                "directly to the file 'bob_response.json' in the current workspace directory. "
                "Output ONLY valid JSON without markdown conversational commentary."
            )

        cmd = [
            self.binary,
            "run",
            "--accept-license",
            "--trust",
            "--workspace", str(workspace),
            "--format", "json",
            "--disable-mcp",
            "--max-turns", "2",
        ]

        env = os.environ.copy()
        if self.api_key:
            env["BOB_API_KEY"] = self.api_key
            env["BOBSHELL_API_KEY"] = self.api_key

        logger.info(
            "Executing IBM Bob headless run (binary: %s, prompt size: %d bytes)",
            self.binary, len(augmented_prompt)
        )

        try:
            result = subprocess.run(
                cmd,
                input=augmented_prompt,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                env=env,
                timeout=self.timeout
            )

            if result.returncode != 0:
                err_msg = (result.stderr or result.stdout or f"Bob CLI exited with code {result.returncode}").strip()
                logger.warning("Bob CLI returned non-zero code %d. Stderr: %s", result.returncode, result.stderr)
                return BobExecutionResult(
                    is_success=False,
                    error=f"Bob CLI execution failed (exit code {result.returncode}): {err_msg}"
                )

            # 1. Extract text and stats from stdout & artifacts
            stats = self._extract_stats(result.stdout)
            task_id = stats.get("task_id", "")
            duration_ms = int(stats.get("duration_ms", 0))
            raw_cost = float(stats.get("session_costs", 0.0))

            text = self._extract_text(result.stdout, workspace)

            # 2. Extract token counts and exact cost telemetry
            input_tokens, output_tokens, total_tokens, cost_usd = self._extract_tokens_and_cost(
                task_id=task_id,
                default_cost=raw_cost,
                prompt=prompt,
                response_text=text
            )

            # 3. If json_mode, attempt robust parsing
            parsed_json = None
            if json_mode:
                parsed_json = self._parse_json(text)

            return BobExecutionResult(
                text=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                duration_ms=duration_ms,
                task_id=task_id,
                is_success=True,
                json_data=parsed_json,
            )

        except subprocess.TimeoutExpired:
            logger.error("Bob CLI execution timed out after %ds", self.timeout)
            return BobExecutionResult(
                is_success=False,
                error=f"Bob execution timed out after {self.timeout}s"
            )
        except Exception as e:
            logger.exception("Error executing Bob CLI: %s", str(e))
            return BobExecutionResult(
                is_success=False,
                error=f"Failed to execute IBM Bob: {str(e)}"
            )
        finally:
            shutil.rmtree(workspace_dir, ignore_errors=True)

    def _extract_stats(self, stdout: str) -> Dict[str, Any]:
        """Extracts stats dict containing task_id and session_costs from Bob output."""
        if not stdout:
            return {}
        for line in reversed(stdout.strip().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict) and "stats" in data:
                    return data["stats"]
            except Exception:
                pass
        return {}

    def _extract_text(self, stdout: str, workspace: Path) -> str:
        """Extracts text response from file artifact or event stream."""
        # Check if bob_response.json or bob_review.json was created
        for fname in ["bob_response.json", "bob_review.json"]:
            report_file = workspace / fname
            if report_file.is_file():
                try:
                    content = report_file.read_text(encoding="utf-8").strip()
                    if content:
                        return content
                except Exception:
                    pass

        # Scan for last_message in event stream
        if not stdout:
            return ""

        for line in reversed(stdout.strip().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict) and "last_message" in data:
                    return data["last_message"]
            except Exception:
                pass

        return stdout.strip()

    def _extract_tokens_and_cost(
        self,
        task_id: str,
        default_cost: float,
        prompt: str,
        response_text: str,
    ) -> Tuple[int, int, int, float]:
        """Resolves input tokens, output tokens, total tokens, and USD cost from logs or sqlite database."""
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        cost_usd = default_cost

        # 1. Search recent Bob Shell log files for the task's json-renderer cost message
        log_dir = os.path.expanduser("~/.bob/logs/shell")
        if os.path.isdir(log_dir) and task_id:
            try:
                log_files = sorted(glob(os.path.join(log_dir, "bob-shell-*.log")), key=os.path.getmtime, reverse=True)
                for lf in log_files[:5]:
                    with open(lf, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if task_id in content:
                        for line in content.splitlines():
                            if "costs" in line and "input" in line:
                                try:
                                    data = json.loads(line)
                                    costs_data = data.get("costs")
                                    if not costs_data and "msg" in data:
                                        inner = json.loads(data["msg"])
                                        costs_data = inner.get("costs")
                                    if costs_data:
                                        input_tokens = int(costs_data.get("input", 0))
                                        output_tokens = int(costs_data.get("output", 0))
                                        cost_usd = float(costs_data.get("cost", default_cost))
                                        total_tokens = int(costs_data.get("contextTokens", input_tokens + output_tokens))
                                        return input_tokens, output_tokens, total_tokens, cost_usd
                                except Exception:
                                    pass
            except Exception as e:
                logger.debug("Could not inspect bob log file: %s", e)

        # 2. Check local SQLite DB ~/.bob/db/bob.db
        db_path = os.path.expanduser("~/.bob/db/bob.db")
        if os.path.exists(db_path) and task_id:
            try:
                con = sqlite3.connect(db_path)
                cur = con.cursor()
                row = cur.execute("SELECT costs FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if row and row[0]:
                    c_data = json.loads(row[0])
                    cost_usd = float(c_data.get("cost", default_cost))
                    total_tokens = int(c_data.get("contextTokens", 0))
                    if total_tokens > 0:
                        # Estimate output tokens from response length (~4 chars/token)
                        output_tokens = max(1, len(response_text) // 4)
                        input_tokens = max(0, total_tokens - output_tokens)
                        con.close()
                        return input_tokens, output_tokens, total_tokens, cost_usd
                con.close()
            except Exception as e:
                logger.debug("Could not query bob.db: %s", e)

        # 3. Fallback estimation based on text length if log not yet flushed
        if input_tokens == 0:
            input_tokens = max(1, len(prompt) // 4)
        if output_tokens == 0:
            output_tokens = max(1, len(response_text) // 4)
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens

        # Fallback cost estimation if default_cost is 0 ($2 per 1M input, $8 per 1M output)
        if cost_usd == 0.0:
            cost_usd = round((input_tokens * 0.000002) + (output_tokens * 0.000008), 6)

        return input_tokens, output_tokens, total_tokens, cost_usd

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Progressive fallbacks to parse JSON from text (fences, stream search, raw decode)."""
        if not text:
            return None

        # Strategy 1: Markdown fenced block ```json ... ```
        fence_matches = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        for chunk in reversed(fence_matches):
            try:
                return json.loads(chunk.strip())
            except Exception:
                pass

        # Strategy 2: Raw decode from first '{'
        decoder = json.JSONDecoder()
        pos = text.find("{")
        while pos != -1:
            try:
                obj, _ = decoder.raw_decode(text[pos:])
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
            pos = text.find("{", pos + 1)

        # Strategy 3: Direct parse
        try:
            return json.loads(text.strip())
        except Exception:
            pass

        return None
