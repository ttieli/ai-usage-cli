from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .base import BaseProvider, CostInfo, RateWindow, UsageResult, format_duration, read_keychain


class ClaudeProvider(BaseProvider):
    name = "Claude"
    config_id = "claude"

    async def fetch(self, config: dict) -> UsageResult:
        result = UsageResult(provider=self.name)
        token = self._get_token()
        if not token:
            result.error = "No OAuth token found (Keychain or ~/.claude/.credentials.json)"
            return result

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.anthropic.com/api/oauth/usage",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "anthropic-beta": "oauth-2025-04-20",
                    },
                )
                if resp.status_code == 401:
                    result.error = "OAuth token expired or missing user:profile scope"
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
        self._parse_identity(result)
        self._parse_usage(data, result)
        return result

    def _get_token(self) -> str | None:
        raw = read_keychain("Claude Code-credentials")
        if raw:
            try:
                creds = json.loads(raw)
                oauth = creds.get("claudeAiOauth", {})
                return oauth.get("accessToken")
            except (json.JSONDecodeError, KeyError):
                pass

        cred_file = Path.home() / ".claude" / ".credentials.json"
        if cred_file.exists():
            try:
                creds = json.loads(cred_file.read_text())
                oauth = creds.get("claudeAiOauth", {})
                return oauth.get("accessToken")
            except (json.JSONDecodeError, KeyError):
                pass
        return None

    def _parse_identity(self, result: UsageResult) -> None:
        raw = read_keychain("Claude Code-credentials")
        if not raw:
            return
        try:
            creds = json.loads(raw)
            oauth = creds.get("claudeAiOauth", {})
            result.email = oauth.get("email", "")
            tier_lower = (oauth.get("rateLimitTier") or "").lower()
            if "max" in tier_lower:
                result.plan = "Max"
            elif "pro" in tier_lower:
                result.plan = "Pro"
            elif "team" in tier_lower:
                result.plan = "Team"
            elif "enterprise" in tier_lower:
                result.plan = "Enterprise"
            elif "free" in tier_lower:
                result.plan = "Free"
            else:
                result.plan = ""
        except (json.JSONDecodeError, KeyError):
            pass

    def _parse_usage(self, data: dict, result: UsageResult) -> None:
        for key, label in [
            ("five_hour", "Session (5h)"),
            ("seven_day", "Weekly (7d)"),
            ("seven_day_sonnet", "Sonnet (7d)"),
            ("seven_day_opus", "Opus (7d)"),
            ("seven_day_oauth_apps", "OAuth apps (7d)"),
        ]:
            window = data.get(key)
            if not window:
                continue
            utilization = window.get("utilization")
            if utilization is None:
                continue
            used_pct = round(utilization, 1)  # API returns 0-100 directly
            resets_at = ""
            if window.get("resets_at"):
                try:
                    dt = datetime.fromisoformat(window["resets_at"].replace("Z", "+00:00"))
                    delta = dt - datetime.now(timezone.utc)
                    resets_at = format_duration(delta.total_seconds())
                except (ValueError, TypeError):
                    pass
            result.windows.append(RateWindow(
                label=label,
                used_percent=used_pct,
                resets_at=resets_at,
            ))

        result.cost = self._parse_extra_usage(data.get("extra_usage"), result.plan)

    @staticmethod
    def _parse_extra_usage(extra: dict | None, plan: str) -> CostInfo | None:
        # Claude OAuth's extra_usage block: only meaningful when explicitly enabled
        # and both used_credits + monthly_limit are populated. The API reports
        # amounts in cents, so convert to dollars; non-enterprise plans sometimes
        # report another 100x inflation, rescale when the result still looks too high.
        if not extra or extra.get("is_enabled") is not True:
            return None
        used = extra.get("used_credits")
        limit = extra.get("monthly_limit")
        if used is None or limit is None:
            return None

        used_dollars = used / 100.0
        limit_dollars = limit / 100.0

        if "enterprise" not in plan.lower() and limit_dollars >= 1000:
            used_dollars /= 100.0
            limit_dollars /= 100.0

        currency = (extra.get("currency") or "USD").strip() or "USD"
        return CostInfo(
            used=used_dollars,
            limit=limit_dollars,
            currency=currency,
            period="monthly",
        )
