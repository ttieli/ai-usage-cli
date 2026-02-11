from __future__ import annotations

import os

import httpx

from .base import BaseProvider, RateWindow, UsageResult


class ZaiProvider(BaseProvider):
    name = "z.ai"
    config_id = "zai"

    async def fetch(self, config: dict) -> UsageResult:
        result = UsageResult(provider=self.name)
        api_key = self._get_api_key(config)
        if not api_key:
            result.error = "No API key (set Z_AI_API_KEY or configure in CodexBar)"
            return result

        host = os.environ.get("Z_AI_API_HOST", "")
        url = os.environ.get("Z_AI_QUOTA_URL", "")
        if not url:
            if host:
                url = f"https://{host}/api/monitor/usage/quota/limit"
            else:
                url = "https://open.bigmodel.cn/api/monitor/usage/quota/limit"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 401:
                    result.error = "API key invalid"
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
        self._parse_quota(data, result)
        return result

    def _get_api_key(self, config: dict) -> str | None:
        key = os.environ.get("Z_AI_API_KEY")
        if key:
            return key
        pc = self.get_provider_config(config)
        return pc.get("apiKey")

    def _parse_quota(self, data: dict, result: UsageResult) -> None:
        payload = data.get("data", data)
        if isinstance(payload, dict):
            used = payload.get("used", 0)
            limit = payload.get("limit", 0)
            if limit and limit > 0:
                used_pct = round(used / limit * 100, 1)
            else:
                used_pct = 0
            result.windows.append(RateWindow(
                label="Quota",
                used_percent=used_pct,
            ))
        elif isinstance(payload, list):
            for item in payload:
                name = item.get("name", "Quota")
                used = item.get("used", 0)
                limit = item.get("limit", 0)
                if limit and limit > 0:
                    used_pct = round(used / limit * 100, 1)
                else:
                    used_pct = 0
                result.windows.append(RateWindow(
                    label=name,
                    used_percent=used_pct,
                ))
