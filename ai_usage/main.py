from __future__ import annotations

import argparse
import asyncio
import ssl
import sys

import truststore
truststore.inject_into_ssl()

from rich.console import Console

from .display import render_json, render_plain, render_text
from .providers import ALL_PROVIDERS
from .providers.base import UsageResult, load_codexbar_config


async def fetch_all(
    provider_names: list[str] | None,
    enabled_only: bool,
) -> list[UsageResult]:
    config = load_codexbar_config()
    providers = []

    for cls in ALL_PROVIDERS:
        p = cls()
        if provider_names:
            if p.config_id in provider_names or p.name.lower() in provider_names:
                providers.append(p)
        elif enabled_only:
            if p.is_enabled(config):
                providers.append(p)
        else:
            providers.append(p)

    tasks = [p.fetch(config) for p in providers]
    return list(await asyncio.gather(*tasks))


PROVIDER_IDS = [cls.config_id for cls in [c() for c in ALL_PROVIDERS]]

HELP_EPILOG = f"""\
Supported providers:
  {', '.join(PROVIDER_IDS)}

Examples:
  ai-usage                    all enabled providers
  ai-usage -p claude          single provider
  ai-usage -p claude codex    multiple providers
  ai-usage -a                 include disabled providers
  ai-usage --json             JSON output (for scripting)
  ai-usage --plain            plain text (no color, no unicode)
  ai-usage | grep Claude      auto-switches to plain when piped

Credential sources:
  Claude   macOS Keychain "Claude Code-credentials" or ~/.claude/.credentials.json
  Codex    ~/.codex/auth.json (auto-refreshes OAuth token)
  Gemini   ~/.gemini/oauth_creds.json (auto-refreshes OAuth token)
  Copilot  apiKey in ~/.codexbar/config.json
  z.ai     apiKey in ~/.codexbar/config.json or Z_AI_API_KEY env var

Config: ~/.codexbar/config.json (enable/disable providers, API keys, etc.)
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ai-usage",
        description="Check AI coding tool usage quotas (Claude, Codex, Gemini, Copilot, z.ai)",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-p", "--provider",
        nargs="*",
        metavar="NAME",
        help="provider(s) to query (e.g. claude codex gemini)",
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="query all providers (including disabled ones)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="JSON output",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="plain text output (no color, no unicode; for piping)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="keep unicode but disable color",
    )
    args = parser.parse_args()

    # Auto-detect: if stdout is not a TTY (piped), default to plain
    is_pipe = not sys.stdout.isatty()
    use_plain = args.plain or (is_pipe and not args.json_output)

    console = Console(no_color=args.no_color)

    provider_names = None
    if args.provider:
        provider_names = [n.lower() for n in args.provider]

    enabled_only = not args.all and provider_names is None

    try:
        results = asyncio.run(fetch_all(provider_names, enabled_only))
    except KeyboardInterrupt:
        sys.exit(130)

    if not results:
        if use_plain:
            print("No providers to check. Use --all or -p <name>.")
        else:
            console.print("[dim]No providers to check.[/dim]")
            console.print("[dim]Use --all to check all providers, or -p <name> to pick one.[/dim]")
        sys.exit(0)

    if args.json_output:
        render_json(results, console)
    elif use_plain:
        render_plain(results)
    else:
        render_text(results, console)

    has_error = any(r.error for r in results)
    sys.exit(1 if has_error and not any(r.windows for r in results) else 0)


if __name__ == "__main__":
    main()
