import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import httpx

from ai_usage import main as main_module
from ai_usage.providers import ALL_PROVIDERS
from ai_usage.providers.base import UsageResult
from ai_usage.providers.opencode_go import OpenCodeGoProvider


class OpenCodeGoRegistrationTests(unittest.TestCase):
    def test_provider_is_registered_under_public_cli_id(self) -> None:
        provider_ids = [provider_class().config_id for provider_class in ALL_PROVIDERS]

        self.assertIn("opencode-go", provider_ids)


class OpenCodeGoHelpTests(unittest.TestCase):
    def test_help_metadata_identifies_opencode_go(self) -> None:
        self.assertIn("opencode-go", main_module.PROVIDER_IDS)
        self.assertIn("opencode-go", main_module.HELP_EPILOG)
        self.assertIn(
            "~/.local/share/opencode/auth.json",
            main_module.HELP_EPILOG,
        )
        self.assertIn(
            "OpenCode Go",
            getattr(main_module, "PROGRAM_DESCRIPTION", ""),
        )


class OpenCodeGoCredentialTests(unittest.TestCase):
    def test_reads_api_key_from_opencode_auth_content(self) -> None:
        content = json.dumps(
            {"opencode-go": {"type": "api", "key": "secret-test-key"}}
        )

        with mock.patch.dict(
            os.environ,
            {"OPENCODE_AUTH_CONTENT": content},
            clear=True,
        ):
            provider = OpenCodeGoProvider()
            self.assertTrue(hasattr(provider, "_load_api_key"))
            self.assertEqual(
                provider._load_api_key(),
                "secret-test-key",
            )

    def test_reads_api_key_from_xdg_data_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth_path = Path(directory) / "opencode" / "auth.json"
            auth_path.parent.mkdir(parents=True)
            auth_path.write_text(
                json.dumps(
                    {"opencode-go": {"type": "api", "key": "xdg-test-key"}}
                )
            )

            with mock.patch.dict(
                os.environ,
                {"XDG_DATA_HOME": directory},
                clear=True,
            ):
                provider = OpenCodeGoProvider()
                self.assertTrue(hasattr(provider, "_load_api_key"))
                self.assertEqual(
                    provider._load_api_key(),
                    "xdg-test-key",
                )

    def test_malformed_auth_content_is_unavailable(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"OPENCODE_AUTH_CONTENT": "not-json"},
            clear=True,
        ):
            provider = OpenCodeGoProvider()
            self.assertTrue(hasattr(provider, "_load_api_key"))
            self.assertIsNone(provider._load_api_key())

    def test_missing_opencode_go_entry_is_unavailable(self) -> None:
        content = json.dumps({"zhipuai": {"type": "api", "key": "other-key"}})

        with mock.patch.dict(
            os.environ,
            {"OPENCODE_AUTH_CONTENT": content},
            clear=True,
        ):
            provider = OpenCodeGoProvider()
            self.assertTrue(hasattr(provider, "_load_api_key"))
            self.assertIsNone(provider._load_api_key())

    def test_non_api_opencode_go_entry_is_unavailable(self) -> None:
        content = json.dumps(
            {"opencode-go": {"type": "oauth", "access": "oauth-test-token"}}
        )

        with mock.patch.dict(
            os.environ,
            {"OPENCODE_AUTH_CONTENT": content},
            clear=True,
        ):
            provider = OpenCodeGoProvider()
            self.assertTrue(hasattr(provider, "_load_api_key"))
            self.assertIsNone(provider._load_api_key())


class OpenCodeGoEnablementTests(unittest.TestCase):
    def test_explicit_codexbar_disable_wins_over_existing_credential(self) -> None:
        content = json.dumps(
            {"opencode-go": {"type": "api", "key": "test-key"}}
        )
        config = {"providers": [{"id": "opencodego", "enabled": False}]}

        with mock.patch.dict(
            os.environ,
            {"OPENCODE_AUTH_CONTENT": content},
            clear=True,
        ):
            self.assertFalse(OpenCodeGoProvider().is_enabled(config))

    def test_explicit_codexbar_enable_does_not_require_credential_probe(self) -> None:
        config = {"providers": [{"id": "opencodego", "enabled": True}]}

        with mock.patch.dict(
            os.environ,
            {"OPENCODE_AUTH_CONTENT": "not-json"},
            clear=True,
        ):
            self.assertTrue(OpenCodeGoProvider().is_enabled(config))

    def test_existing_credential_enables_provider_when_config_is_absent(self) -> None:
        content = json.dumps(
            {"opencode-go": {"type": "api", "key": "test-key"}}
        )

        with mock.patch.dict(
            os.environ,
            {"OPENCODE_AUTH_CONTENT": content},
            clear=True,
        ):
            self.assertTrue(OpenCodeGoProvider().is_enabled({}))


class OpenCodeGoUsageTests(unittest.TestCase):
    auth_content = json.dumps(
        {"opencode-go": {"type": "api", "key": "test-key"}}
    )

    def provider_with_transport(
        self,
        transport: httpx.AsyncBaseTransport,
    ) -> OpenCodeGoProvider:
        try:
            return OpenCodeGoProvider(transport=transport)
        except TypeError as error:
            self.fail(f"OpenCodeGoProvider does not accept a transport: {error}")

    def test_fetches_official_usage_windows(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "GET")
            self.assertEqual(
                str(request.url),
                "https://opencode.ai/zen/go/v1/usage",
            )
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            return httpx.Response(
                200,
                json={
                    "usage": {
                        "rolling": {
                            "status": "ok",
                            "percent": 25,
                            "resetsAt": "2026-08-30T15:00:00Z",
                        },
                        "weekly": {
                            "status": "rate-limited",
                            "percent": 100,
                            "resetsAt": "2026-08-31T00:00:00Z",
                        },
                        "monthly": {
                            "status": "ok",
                            "percent": 54.4,
                            "resetsAt": "2026-09-07T00:00:00Z",
                        },
                    }
                },
            )

        provider = self.provider_with_transport(httpx.MockTransport(handler))
        with mock.patch.dict(
            os.environ,
            {"OPENCODE_AUTH_CONTENT": self.auth_content},
            clear=True,
        ):
            result = asyncio.run(provider.fetch({}))

        self.assertIsNone(result.error)
        self.assertEqual(result.provider, "OpenCode Go")
        self.assertEqual(result.source, "api")
        self.assertEqual(result.plan, "Go")
        self.assertEqual(
            [window.label for window in result.windows],
            ["Rolling", "Weekly", "Monthly"],
        )
        self.assertEqual(
            [window.used_percent for window in result.windows],
            [25.0, 100.0, 54.4],
        )

    def test_maps_auth_and_subscription_errors(self) -> None:
        expected_errors = {
            401: "OpenCode Go API key invalid",
            403: "OpenCode Go subscription required",
            500: "HTTP 500",
        }

        for status_code, expected_error in expected_errors.items():
            with self.subTest(status_code=status_code):
                transport = httpx.MockTransport(
                    lambda request, code=status_code: httpx.Response(
                        code,
                        json={"error": {"message": "server detail"}},
                    )
                )
                provider = self.provider_with_transport(transport)
                with mock.patch.dict(
                    os.environ,
                    {"OPENCODE_AUTH_CONTENT": self.auth_content},
                    clear=True,
                ):
                    result = asyncio.run(provider.fetch({}))

                self.assertEqual(result.error, expected_error)
                self.assertEqual(result.windows, [])

    def test_rejects_usage_response_without_windows(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"usage": []})
        )
        provider = self.provider_with_transport(transport)

        with mock.patch.dict(
            os.environ,
            {"OPENCODE_AUTH_CONTENT": self.auth_content},
            clear=True,
        ):
            result = asyncio.run(provider.fetch({}))

        self.assertEqual(result.error, "Invalid OpenCode Go usage response")
        self.assertEqual(result.windows, [])

    def test_maps_connection_error_without_exposing_credentials(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("network unavailable", request=request)

        provider = self.provider_with_transport(httpx.MockTransport(handler))
        with mock.patch.dict(
            os.environ,
            {"OPENCODE_AUTH_CONTENT": self.auth_content},
            clear=True,
        ):
            result = asyncio.run(provider.fetch({}))

        self.assertEqual(result.error, "network unavailable")
        self.assertNotIn("test-key", result.error)

    def test_parses_reset_durations_and_clamps_percentages(self) -> None:
        provider = OpenCodeGoProvider()
        result = UsageResult(provider=provider.name)
        now = datetime(2026, 8, 30, 14, 0, tzinfo=timezone.utc)
        data = {
            "usage": {
                "rolling": {
                    "percent": -5,
                    "resetsAt": "2026-08-30T15:00:00Z",
                },
                "weekly": {
                    "percent": 105,
                    "resetsAt": "2026-08-31T00:00:00Z",
                },
                "monthly": {
                    "percent": 54.4,
                    "resetsAt": "not-a-date",
                },
            }
        }

        self.assertTrue(hasattr(provider, "_parse_usage"))
        provider._parse_usage(data, result, now=now)

        self.assertEqual(
            [window.used_percent for window in result.windows],
            [0.0, 100.0, 54.4],
        )
        self.assertEqual(
            [window.resets_at for window in result.windows],
            ["1h0m", "10h0m", ""],
        )


if __name__ == "__main__":
    unittest.main()
