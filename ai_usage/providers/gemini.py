from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .base import BaseProvider, RateWindow, UsageResult


class GeminiProvider(BaseProvider):
    name = "Gemini"
    config_id = "gemini"

    async def fetch(self, config: dict) -> UsageResult:
        result = UsageResult(provider=self.name)
        creds = self._load_creds()
        if not creds:
            result.error = "No credentials at ~/.gemini/oauth_creds.json"
            return result

        token = creds.get("access_token", "")
        if not token:
            result.error = "No access_token in credentials"
            return result

        # Check if token is expired and try refresh
        expiry = creds.get("expiry_date", 0)
        if expiry and expiry / 1000 < datetime.now(timezone.utc).timestamp():
            refreshed = await self._refresh_token(creds)
            if refreshed:
                token = refreshed
            else:
                result.error = "Token expired, refresh failed"
                return result

        project_id = await self._find_project(token)

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                body = {"project": project_id} if project_id else {}
                resp = await client.post(
                    "https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota",
                    headers={"Authorization": f"Bearer {token}"},
                    json=body,
                )
                if resp.status_code == 401:
                    result.error = "Token expired or invalid"
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
        self._parse_quota(data, result)
        self._parse_identity(creds, result)
        return result

    def _load_creds(self) -> dict | None:
        path = Path.home() / ".gemini" / "oauth_creds.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None

    def _parse_identity(self, creds: dict, result: UsageResult) -> None:
        id_token = creds.get("id_token", "")
        if id_token:
            try:
                import base64
                parts = id_token.split(".")
                if len(parts) >= 2:
                    padded = parts[1] + "=" * (-len(parts[1]) % 4)
                    claims = json.loads(base64.urlsafe_b64decode(padded))
                    result.email = claims.get("email", "")
            except Exception:
                pass

    async def _refresh_token(self, creds: dict) -> str | None:
        refresh_token = creds.get("refresh_token")
        if not refresh_token:
            return None

        client_id, client_secret = self._extract_oauth_client()
        if not client_id:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                new_token = data.get("access_token")
                if new_token:
                    # Update cached credentials
                    creds["access_token"] = new_token
                    path = Path.home() / ".gemini" / "oauth_creds.json"
                    path.write_text(json.dumps(creds, indent=2))
                return new_token
        except Exception:
            return None

    def _extract_oauth_client(self) -> tuple[str | None, str | None]:
        gemini_bin = shutil.which("gemini")
        if not gemini_bin:
            return None, None

        gemini_path = Path(gemini_bin).resolve()
        search_paths = [
            gemini_path.parent.parent
            / "libexec/lib/node_modules/@google/gemini-cli/node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js",
            gemini_path.parent.parent
            / "node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js",
        ]

        for p in search_paths:
            if p.exists():
                content = p.read_text()
                id_match = re.search(r'OAUTH_CLIENT_ID\s*=\s*["\']([^"\']+)', content)
                secret_match = re.search(
                    r'OAUTH_CLIENT_SECRET\s*=\s*["\']([^"\']+)', content
                )
                if id_match and secret_match:
                    return id_match.group(1), secret_match.group(1)
        return None, None

    async def _find_project(self, token: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"metadata": {"ideType": "GEMINI_CLI", "pluginType": "GEMINI"}},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    project = data.get("cloudaicompanionProject")
                    tier = data.get("tier", "")
                    self._tier = tier
                    return project
        except Exception:
            pass
        self._tier = ""
        return None

    def _parse_quota(self, data: dict, result: UsageResult) -> None:
        tier = getattr(self, "_tier", "")
        tier_map = {
            "standard-tier": "Paid",
            "free-tier": "Free",
            "legacy-tier": "Legacy",
        }
        result.plan = tier_map.get(tier, tier.title() if tier else "")

        buckets = data.get("userQuotaBuckets", [])
        if not buckets:
            result.windows.append(RateWindow(
                label="Daily quota",
                used_percent=0.0,
                resets_at="",
            ))
            return

        # Group by model category
        pro_remaining = 1.0
        flash_remaining = 1.0
        pro_reset = ""
        flash_reset = ""
        has_pro = False
        has_flash = False

        for bucket in buckets:
            remaining = bucket.get("remainingFraction", 1.0)
            model_id = bucket.get("modelId", "")
            reset_time = bucket.get("resetTime", "")
            reset_str = ""
            if reset_time:
                try:
                    dt = datetime.fromisoformat(reset_time.replace("Z", "+00:00"))
                    delta = dt - datetime.now(timezone.utc)
                    hours = int(delta.total_seconds() // 3600)
                    minutes = int((delta.total_seconds() % 3600) // 60)
                    if delta.total_seconds() > 0:
                        reset_str = f"{hours}h{minutes}m"
                except (ValueError, TypeError):
                    pass

            is_flash = "flash" in model_id.lower()
            if is_flash:
                has_flash = True
                if remaining < flash_remaining:
                    flash_remaining = remaining
                    flash_reset = reset_str
            else:
                has_pro = True
                if remaining < pro_remaining:
                    pro_remaining = remaining
                    pro_reset = reset_str

        if has_pro:
            result.windows.append(RateWindow(
                label="Pro models",
                used_percent=round((1 - pro_remaining) * 100, 1),
                resets_at=pro_reset,
            ))
        if has_flash:
            result.windows.append(RateWindow(
                label="Flash models",
                used_percent=round((1 - flash_remaining) * 100, 1),
                resets_at=flash_reset,
            ))
