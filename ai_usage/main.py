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
支持的 Provider:
  {', '.join(PROVIDER_IDS)}

示例:
  ai-usage                    查看所有已启用的 Provider
  ai-usage -p claude          只看 Claude
  ai-usage -p claude codex    看 Claude 和 Codex
  ai-usage -a                 包含未启用的 Provider
  ai-usage --json             JSON 输出（适合脚本处理）
  ai-usage --plain            纯文本输出（无颜色、无 Unicode）
  ai-usage | grep Claude      管道时自动切换纯文本模式

凭据来源:
  Claude   macOS Keychain "Claude Code-credentials" 或 ~/.claude/.credentials.json
  Codex    ~/.codex/auth.json（自动刷新 token）
  Gemini   ~/.gemini/oauth_creds.json（自动刷新 token）
  Copilot  ~/.codexbar/config.json 中的 apiKey（需先通过 CodexBar 登录）
  z.ai     ~/.codexbar/config.json 中的 apiKey 或 Z_AI_API_KEY 环境变量

配置文件: ~/.codexbar/config.json（控制 Provider 启用/禁用、API key 等）
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ai-usage",
        description="查询 AI 编程工具的配额用量（Claude, Codex, Gemini, Copilot, z.ai）",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-p", "--provider",
        nargs="*",
        metavar="NAME",
        help="指定要查询的 Provider（可多个，如 claude codex gemini）",
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="查询所有 Provider（包含未启用的）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="JSON 格式输出",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="纯文本输出（无颜色、无 Unicode，适合管道和脚本）",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="保留 Unicode 但关闭颜色",
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
