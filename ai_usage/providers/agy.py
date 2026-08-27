from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import httpx

from .base import BaseProvider, RateWindow, UsageResult, format_duration, read_keychain


class AgyProvider(BaseProvider):
    name = "Antigravity (AGY)"
    config_id = "agy"

    async def fetch(self, config: dict) -> UsageResult:
        result = UsageResult(provider=self.name)
        token_data, raw_token = self._get_token()

        # Read active model and settings from ~/.gemini/antigravity-cli/settings.json
        model_name = self._get_active_model()
        email = self._get_email(token_data)

        if not raw_token and not email:
            result.error = "Not logged in (run agy to authenticate)"
            return result

        result.source = "oauth"
        result.email = email
        result.plan = "Standard"

        # Calculate rolling session stats from history
        stats_5h = self._get_session_stats(hours=5)

        is_flash_active = "flash" in model_name.lower()
        is_claude_active = "claude" in model_name.lower() or "pro" in model_name.lower()

        # 1. Flash Models Window
        flash_used_pct = 0.0
        flash_reset = ""
        if is_flash_active and stats_5h["turn_count"] > 0:
            # Approximate utilization based on standard 5h rolling cap (~50 turns per 5h window)
            flash_used_pct = min(99.0, round((stats_5h["turn_count"] / 50.0) * 100, 1))
            flash_reset = stats_5h["reset_str"]
        elif not is_flash_active:
            flash_used_pct = 0.0
            flash_reset = ""

        flash_label = f"Flash ({model_name})" if is_flash_active else "Flash models"
        result.windows.append(
            RateWindow(
                label=flash_label,
                used_percent=flash_used_pct,
                resets_at=flash_reset,
            )
        )

        # 2. Claude & Pro Models Window
        claude_used_pct = 0.0
        claude_reset = ""
        if is_claude_active and stats_5h["turn_count"] > 0:
            claude_used_pct = min(99.0, round((stats_5h["turn_count"] / 30.0) * 100, 1))
            claude_reset = stats_5h["reset_str"]

        claude_label = f"Claude & Pro ({model_name})" if is_claude_active else "Claude & Pro models"
        result.windows.append(
            RateWindow(
                label=claude_label,
                used_percent=claude_used_pct,
                resets_at=claude_reset,
            )
        )

        return result

    def _get_session_stats(self, hours: int = 5) -> dict:
        history_path = Path.home() / ".gemini" / "antigravity-cli" / "history.jsonl"
        now_ms = datetime.now(timezone.utc).timestamp() * 1000
        window_ms = hours * 3600 * 1000

        recent_count = 0
        oldest_in_window = now_ms

        if history_path.exists():
            try:
                for line in history_path.read_text(errors="ignore").splitlines():
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    ts = entry.get("timestamp") or entry.get("created_at")
                    if ts:
                        if isinstance(ts, str):
                            try:
                                ts = int(ts)
                            except ValueError:
                                continue
                        diff = now_ms - ts
                        if diff <= window_ms and diff >= 0:
                            recent_count += 1
                            if ts < oldest_in_window:
                                oldest_in_window = ts
            except Exception:
                pass

        reset_str = ""
        if recent_count > 0:
            reset_secs = max(0, (oldest_in_window + window_ms - now_ms) / 1000)
            if reset_secs > 0:
                reset_str = format_duration(reset_secs)

        return {
            "turn_count": recent_count,
            "reset_str": reset_str,
        }

    def _get_active_model(self) -> str:
        settings_path = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"
        if settings_path.exists():
            try:
                s = json.loads(settings_path.read_text())
                model = s.get("model")
                if model:
                    return model
            except Exception:
                pass
        return "Gemini 3.7 Flash"

    def _get_email(self, token_data: Optional[dict]) -> str:
        if token_data:
            id_token = token_data.get("id_token") or token_data.get("access_token", "")
            try:
                parts = id_token.split(".")
                if len(parts) >= 2:
                    padded = parts[1] + "=" * (-len(parts[1]) % 4)
                    claims = json.loads(base64.urlsafe_b64decode(padded))
                    if claims.get("email"):
                        return claims["email"]
            except Exception:
                pass

        # Fallback: scan recent agy logs for email
        log_dir = Path.home() / ".gemini" / "antigravity-cli" / "log"
        if log_dir.exists():
            try:
                logs = sorted(log_dir.glob("cli-*.log"), key=os.path.getmtime, reverse=True)
                for log_file in logs[:3]:
                    content = log_file.read_text(errors="ignore")
                    m = re.search(r"authenticated successfully as ([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", content)
                    if m:
                        return m.group(1)
            except Exception:
                pass

        return ""

    def _get_token(self) -> Tuple[Optional[dict], Optional[str]]:
        # 1. Try macOS Keychain
        raw_keychain = read_keychain("gemini-antigravity") or read_keychain("antigravity")
        if raw_keychain:
            try:
                data = json.loads(raw_keychain)
                token = data.get("token", {})
                return token, token.get("access_token")
            except Exception:
                pass

        # 2. Try Linux libsecret / DBus SecretService via gi
        try:
            import gi
            gi.require_version("Secret", "1")
            from gi.repository import Secret

            schema = Secret.Schema.new(
                "org.freedesktop.Secret.Generic",
                Secret.SchemaFlags.NONE,
                {
                    "service": Secret.SchemaAttributeType.STRING,
                    "username": Secret.SchemaAttributeType.STRING,
                },
            )
            raw = Secret.password_lookup_sync(schema, {"service": "gemini", "username": "antigravity"}, None)
            if raw:
                data = json.loads(raw)
                token = data.get("token", {})
                return token, token.get("access_token")
        except Exception:
            pass

        # 3. Try python secretstorage / keyring
        try:
            import secretstorage
            bus = secretstorage.dbus_init()
            collection = secretstorage.get_default_collection(bus)
            for item in collection.get_all_items():
                if item.get_attributes().get("service") == "gemini":
                    raw = item.get_secret().decode("utf-8")
                    data = json.loads(raw)
                    token = data.get("token", {})
                    return token, token.get("access_token")
        except Exception:
            pass

        return None, None
