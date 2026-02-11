from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .base import BaseProvider, RateWindow, UsageResult


class CodexProvider(BaseProvider):
    name = "Codex"
    config_id = "codex"

    async def fetch(self, config: dict) -> UsageResult:
        result = UsageResult(provider=self.name)
        auth_data = self._load_auth()
        if not auth_data:
            result.error = "No auth at ~/.codex/auth.json"
            return result

        tokens = auth_data.get("tokens", {})
        token = tokens.get("access_token", "")
        if not token:
            result.error = "No access_token in ~/.codex/auth.json"
            return result

        # Check if token needs refresh (last_refresh older than 8 days)
        needs_refresh = True
        last_refresh_str = auth_data.get("last_refresh", "")
        if last_refresh_str:
            try:
                lr_dt = datetime.fromisoformat(last_refresh_str.replace("Z", "+00:00"))
                needs_refresh = (datetime.now(timezone.utc) - lr_dt).total_seconds() > 8 * 86400
            except (ValueError, TypeError):
                pass
        if needs_refresh:
            refreshed = await self._refresh_token(auth_data)
            if refreshed:
                token = refreshed

        account_id = tokens.get("account_id", "")
        def _headers(t: str) -> dict:
            h = {
                "Authorization": f"Bearer {t}",
                "Accept": "application/json",
                "User-Agent": "ai-usage-cli",
            }
            if account_id:
                h["ChatGPT-Account-Id"] = account_id
            return h

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://chatgpt.com/backend-api/wham/usage",
                    headers=_headers(token),
                )
                if resp.status_code == 401:
                    refreshed = await self._refresh_token(auth_data)
                    if refreshed:
                        resp = await client.get(
                            "https://chatgpt.com/backend-api/wham/usage",
                            headers=_headers(refreshed),
                        )
                    if resp.status_code == 401:
                        result.error = "Token expired, refresh failed"
                        return result
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            result.error = f"HTTP {e.response.status_code}"
            return result
        except httpx.RequestError as e:
            result.error = str(e)
            return result

        result.source = "oauth"
        result.email = data.get("email", "")
        result.plan = data.get("plan_type", "")
        self._parse_usage(data, result)
        return result

    def _load_auth(self) -> dict | None:
        home = os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
        auth_path = Path(home) / "auth.json"
        if not auth_path.exists():
            return None
        try:
            return json.loads(auth_path.read_text())
        except json.JSONDecodeError:
            return None

    async def _refresh_token(self, auth_data: dict) -> str | None:
        tokens = auth_data.get("tokens", {})
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://auth.openai.com/oauth/token",
                    json={
                        "client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "scope": "openid profile email",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    new_token = data.get("access_token")
                    if new_token:
                        tokens["access_token"] = new_token
                        if data.get("id_token"):
                            tokens["id_token"] = data["id_token"]
                        if data.get("refresh_token"):
                            tokens["refresh_token"] = data["refresh_token"]
                        auth_data["last_refresh"] = datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        )
                        home = os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
                        auth_path = Path(home) / "auth.json"
                        auth_path.write_text(json.dumps(auth_data, indent=2))
                    return new_token
        except Exception:
            pass
        return None

    def _parse_usage(self, data: dict, result: UsageResult) -> None:
        # Parse rate_limit (singular) with primary/secondary windows
        for section_key, prefix in [
            ("rate_limit", ""),
            ("code_review_rate_limit", "Review "),
        ]:
            section = data.get(section_key)
            if not section or not isinstance(section, dict):
                continue
            for win_key, label_suffix in [
                ("primary_window", "Session (5h)"),
                ("secondary_window", "Weekly (7d)"),
            ]:
                window = section.get(win_key)
                if not window or not isinstance(window, dict):
                    continue
                used_pct = round(window.get("used_percent", 0), 1)
                resets_at = self._format_reset_seconds(
                    window.get("reset_after_seconds")
                )
                result.windows.append(RateWindow(
                    label=f"{prefix}{label_suffix}",
                    used_percent=used_pct,
                    resets_at=resets_at,
                ))

    def _format_reset_seconds(self, seconds: int | None) -> str:
        if not seconds or seconds <= 0:
            return ""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h{minutes}m"
