from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .base import BaseProvider, RateWindow, UsageResult, format_duration


USAGE_URL = "https://opencode.ai/zen/go/v1/usage"


class OpenCodeGoProvider(BaseProvider):
    name = "OpenCode Go"
    config_id = "opencode-go"

    def __init__(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._transport = transport

    def is_enabled(self, config: dict) -> bool:
        for provider in config.get("providers", []):
            if provider.get("id") == "opencodego":
                return provider.get("enabled", False)
        return self._load_api_key() is not None

    def _load_api_key(self) -> str | None:
        raw = os.environ.get("OPENCODE_AUTH_CONTENT")
        if raw:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return None
        else:
            data_home = Path(
                os.environ.get(
                    "XDG_DATA_HOME",
                    Path.home() / ".local" / "share",
                )
            )
            auth_path = data_home / "opencode" / "auth.json"
            try:
                data = json.loads(auth_path.read_text())
            except (OSError, json.JSONDecodeError):
                return None

        if not isinstance(data, dict):
            return None
        credential = data.get("opencode-go")
        if not isinstance(credential, dict) or credential.get("type") != "api":
            return None
        key = credential.get("key")
        return key.strip() if isinstance(key, str) and key.strip() else None

    async def fetch(self, config: dict) -> UsageResult:
        result = UsageResult(provider=self.name)
        api_key = self._load_api_key()
        if not api_key:
            result.error = "No OpenCode Go API key in OpenCode auth"
            return result

        try:
            async with httpx.AsyncClient(
                timeout=15,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    USAGE_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Accept": "application/json",
                    },
                )
                if response.status_code == 401:
                    result.error = "OpenCode Go API key invalid"
                    return result
                if response.status_code == 403:
                    result.error = "OpenCode Go subscription required"
                    return result
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as error:
            result.error = f"HTTP {error.response.status_code}"
            return result
        except httpx.RequestError as error:
            result.error = str(error)
            return result
        except ValueError:
            result.error = "Invalid OpenCode Go usage response"
            return result

        result.source = "api"
        result.plan = "Go"
        self._parse_usage(data, result)
        if not result.windows:
            result.error = "Invalid OpenCode Go usage response"
        return result

    def _parse_usage(
        self,
        data: dict,
        result: UsageResult,
        now: datetime | None = None,
    ) -> None:
        usage = data.get("usage") if isinstance(data, dict) else None
        if not isinstance(usage, dict):
            return

        reference_time = now or datetime.now(timezone.utc)
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        for key, label in [
            ("rolling", "Rolling"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
        ]:
            window = usage.get(key)
            if not isinstance(window, dict):
                continue
            percent = window.get("percent")
            if isinstance(percent, bool) or not isinstance(percent, (int, float)):
                continue
            used_percent = round(max(0.0, min(100.0, float(percent))), 1)
            resets_at = self._format_reset_time(
                window.get("resetsAt"),
                reference_time,
            )
            result.windows.append(
                RateWindow(
                    label=label,
                    used_percent=used_percent,
                    resets_at=resets_at,
                )
            )

    @staticmethod
    def _format_reset_time(value: object, now: datetime) -> str:
        if not isinstance(value, str) or not value:
            return ""
        try:
            reset_time = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return ""
        if reset_time.tzinfo is None:
            reset_time = reset_time.replace(tzinfo=timezone.utc)
        seconds = (reset_time - now).total_seconds()
        return format_duration(seconds) if seconds > 0 else ""
