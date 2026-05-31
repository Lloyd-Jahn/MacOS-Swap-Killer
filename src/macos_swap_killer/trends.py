from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import SwapInfo, TrendInfo


@dataclass(frozen=True, slots=True)
class TrendSample:
    timestamp: float
    used_gib: float


class TrendStore:
    def __init__(
        self,
        path: Path,
        *,
        window_sec: int,
        growth_threshold_gib: float,
        max_samples: int,
    ) -> None:
        self.path = path
        self.window_sec = window_sec
        self.growth_threshold_gib = growth_threshold_gib
        self.max_samples = max_samples

    def record(self, swap: SwapInfo, *, now: float | None = None) -> TrendInfo:
        current_time = now if now is not None else time.time()
        samples = self._load()

        if swap.used_gib is not None:
            samples.append(TrendSample(timestamp=current_time, used_gib=swap.used_gib))

        cutoff = current_time - self.window_sec
        recent = [sample for sample in samples if sample.timestamp >= cutoff][-self.max_samples :]
        self._write(recent)

        if not recent:
            return TrendInfo(window_sec=self.window_sec, reason="no swap samples available")

        first = recent[0].used_gib
        latest = recent[-1].used_gib
        growth = max(0.0, latest - first)
        triggered = len(recent) >= 2 and growth >= self.growth_threshold_gib
        reason = (
            f"swap grew {growth:.2f} GiB within {self.window_sec}s"
            if triggered
            else f"swap growth {growth:.2f} GiB below {self.growth_threshold_gib:.2f} GiB trend threshold"
        )

        return TrendInfo(
            window_sec=self.window_sec,
            sample_count=len(recent),
            first_used_gib=round(first, 3),
            latest_used_gib=round(latest, 3),
            growth_gib=round(growth, 3),
            triggered=triggered,
            reason=reason,
        )

    def _load(self) -> list[TrendSample]:
        if not self.path.exists():
            return []

        samples: list[TrendSample] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                raw: dict[str, Any] = json.loads(line)
                samples.append(TrendSample(timestamp=float(raw["timestamp"]), used_gib=float(raw["used_gib"])))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return samples

    def _write(self, samples: list[TrendSample]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = "".join(json.dumps({"timestamp": sample.timestamp, "used_gib": sample.used_gib}) + "\n" for sample in samples)
        self.path.write_text(text, encoding="utf-8")
