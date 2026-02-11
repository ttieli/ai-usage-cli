from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RateWindow:
    label: str
    used_percent: float
    window_desc: str = ""
    resets_at: str = ""


@dataclass
class CostInfo:
    used: float = 0.0
    limit: float | None = None
    currency: str = "USD"
    period: str = ""


@dataclass
class UsageResult:
    provider: str
    plan: str = ""
    email: str = ""
    windows: list[RateWindow] = field(default_factory=list)
    cost: CostInfo | None = None
    error: str | None = None
    source: str = ""


class BaseProvider:
    name: str = ""
    config_id: str = ""

    def is_enabled(self, config: dict) -> bool:
        for p in config.get("providers", []):
            if p.get("id") == self.config_id:
                return p.get("enabled", False)
        return False

    def get_provider_config(self, config: dict) -> dict:
        for p in config.get("providers", []):
            if p.get("id") == self.config_id:
                return p
        return {}

    async def fetch(self, config: dict) -> UsageResult:
        raise NotImplementedError


def load_codexbar_config() -> dict:
    path = Path.home() / ".codexbar" / "config.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def read_keychain(service: str) -> str | None:
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None
