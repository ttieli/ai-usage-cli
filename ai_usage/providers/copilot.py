from __future__ import annotations

import httpx

from .base import BaseProvider, RateWindow, UsageResult, load_codexbar_config


class CopilotProvider(BaseProvider):
    name = "Copilot"
    config_id = "copilot"

    async def fetch(self, config: dict) -> UsageResult:
        result = UsageResult(provider=self.name)
        token = self._get_token(config)
        if not token:
            result.error = "No GitHub token (run CodexBar device flow first)"
            return result

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.github.com/copilot_internal/user",
                    headers={
                        "Authorization": f"token {token}",
                        "Accept": "application/json",
                        "Editor-Version": "vscode/1.96.2",
                        "Editor-Plugin-Version": "copilot-chat/0.26.7",
                        "User-Agent": "GitHubCopilotChat/0.26.7",
                        "X-Github-Api-Version": "2025-04-01",
                    },
                )
                if resp.status_code == 401:
                    result.error = "GitHub token expired"
                    return result
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            result.error = f"HTTP {e.response.status_code}"
            return result
        except httpx.RequestError as e:
            result.error = str(e)
            return result

        result.source = "api"
        result.plan = data.get("copilotPlan", "")

        snapshots = data.get("quotaSnapshots", {})
        for key, label in [
            ("premiumInteractions", "Premium"),
            ("chat", "Chat"),
        ]:
            snap = snapshots.get(key, {})
            remaining = snap.get("percent_remaining")
            if remaining is not None:
                result.windows.append(RateWindow(
                    label=label,
                    used_percent=round(100 - remaining, 1),
                ))
        return result

    def _get_token(self, config: dict) -> str | None:
        pc = self.get_provider_config(config)
        token = pc.get("apiKey")
        if token:
            return token
        return None
