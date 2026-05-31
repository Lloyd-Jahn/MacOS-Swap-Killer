from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from .config import AppConfig
from .models import LLMResponse, ProcessSummary, SwapInfo
from .policy import NEVER_KILL_NAMES


SYSTEM_PROMPT = f"""You are a safety classifier for macOS process termination.

Return only valid JSON matching this schema:
{{
  "overall_risk": "low|medium|high",
  "decisions": [
    {{
      "pid": 12345,
      "process_name": "name",
      "action": "TERMINATE|ASK_CONFIRM|IGNORE",
      "risk": "low|medium|high",
      "reason": "short explanation",
      "expected_memory_mb": 512
    }}
  ]
}}

Rules:
- The local program will enforce additional safeguards, but you must still be conservative.
- Use TERMINATE only for low-risk, user-owned helper, renderer, cache, build, test, worker, or background child processes.
- If a process may have unsaved user state, return ASK_CONFIRM or IGNORE.
- If uncertain, return IGNORE or ASK_CONFIRM. Do not guess.
- Never return TERMINATE for these hard-protected macOS processes: {", ".join(sorted(NEVER_KILL_NAMES))}.
- Never return TERMINATE for WindowServer, kernel_task, launchd, loginwindow, Finder, Dock, or SystemUIServer.
- Never return TERMINATE for root/system services, main GUI applications, or processes in critical system paths.
"""


FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class LLMClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def classify(self, swap: SwapInfo, candidates: list[ProcessSummary]) -> LLMResponse:
        if not self.config.api_key:
            raise RuntimeError("MSK_API_KEY is not configured")

        payload = {
            "model": self.config.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_user_payload(swap, candidates)},
            ],
        }

        url = self.config.base_url.rstrip("/") + "/chat/completions"
        with httpx.Client(timeout=self.config.llm_timeout_sec) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return parse_llm_response(content)

    @staticmethod
    def _build_user_payload(swap: SwapInfo, candidates: list[ProcessSummary]) -> str:
        data: dict[str, Any] = {
            "swap": swap.model_dump(),
            "candidate_processes": [candidate.model_dump() for candidate in candidates],
            "instruction": (
                "Classify each candidate. Return TERMINATE only for low-risk helper/background "
                "processes whose termination should be recoverable. Prefer IGNORE or ASK_CONFIRM."
            ),
        }
        return json.dumps(data, ensure_ascii=False)


def parse_llm_response(content: str) -> LLMResponse:
    stripped = content.strip()
    match = FENCE_RE.match(stripped)
    if match:
        stripped = match.group(1).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM response was not valid JSON") from exc
    try:
        return LLMResponse.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("LLM response did not match schema") from exc
