# ai-usage-cli

[![PyPI version](https://img.shields.io/pypi/v/ai-usage-cli)](https://pypi.org/project/ai-usage-cli/)
[![Python](https://img.shields.io/pypi/pyversions/ai-usage-cli)](https://pypi.org/project/ai-usage-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Check your AI coding tool usage quotas from the terminal. Supports **Claude Code**, **Codex**, **Gemini**, **GitHub Copilot**, **z.ai**, and **OpenCode Go**.

```
$ ai-usage

  Claude  (oauth)  [Max]  user@example.com
    Session (5h)         72.0% left  [█████░░░░░░░░░░░░░░░]  resets in 4h12m
    Weekly (7d)          85.0% left  [███░░░░░░░░░░░░░░░░░]  resets in 132h

  Codex  (oauth)  [Plus]
    Daily                95.2% left  [█░░░░░░░░░░░░░░░░░░░]

  Gemini  (oauth)  [Free]
    Per-minute          100.0% left  [░░░░░░░░░░░░░░░░░░░░]
    Daily                88.4% left  [██░░░░░░░░░░░░░░░░░░]  resets in 16h

  OpenCode Go  (api)  [Go]
    Rolling              75.0% left  [█████░░░░░░░░░░░░░░░]  resets in 4h12m
    Weekly               60.0% left  [████████░░░░░░░░░░░░]
    Monthly              90.0% left  [██░░░░░░░░░░░░░░░░░░]
```

## Installation

**Recommended** — install with [pipx](https://pipx.pypa.io/) for an isolated global command:

```bash
pipx install ai-usage-cli
```

Or with pip:

```bash
pip install ai-usage-cli
```

## Usage

```bash
ai-usage                      # all enabled providers
ai-usage -p claude             # single provider
ai-usage -p claude codex       # multiple providers
ai-usage -p opencode-go        # OpenCode Go quota only
ai-usage -a                    # include disabled providers
ai-usage --json                # JSON output (for scripting)
ai-usage --plain               # plain text (no color, no unicode)
ai-usage | grep Claude         # auto-switches to plain when piped
```

## Supported Providers

| Provider | Credential Source |
|----------|-------------------|
| Claude Code | macOS Keychain (`Claude Code-credentials`) or `~/.claude/.credentials.json` |
| Codex | `~/.codex/auth.json` (auto-refreshes OAuth token) |
| Gemini | `~/.gemini/oauth_creds.json` (auto-refreshes OAuth token) |
| GitHub Copilot | `apiKey` in `~/.codexbar/config.json` |
| z.ai | `apiKey` in `~/.codexbar/config.json` or `Z_AI_API_KEY` env var |
| OpenCode Go | `opencode-go` entry in `$XDG_DATA_HOME/opencode/auth.json` (default: `~/.local/share/opencode/auth.json`) |

## Configuration

Provider settings are stored in `~/.codexbar/config.json`. Each provider can be enabled/disabled and configured with API keys where needed.

OpenCode Go uses the credential already managed by OpenCode. Its public CLI ID is `opencode-go`; when CodexBar has an `opencodego` entry, `ai-usage` honors that entry's `enabled` flag. Without an explicit CodexBar entry, an existing OpenCode Go credential enables the provider automatically. OpenCode Go quota is independent of Codex OAuth quota and must be checked separately.

Example:

```json
{
  "providers": {
    "claude": { "enabled": true },
    "codex": { "enabled": true },
    "gemini": { "enabled": true },
    "copilot": { "enabled": false, "apiKey": "ghu_..." },
    "zai": { "enabled": false, "apiKey": "..." }
  }
}
```

## Platform Notes

- **macOS**: Claude credentials are read from the system Keychain. All other providers use file-based credentials and work cross-platform.
- **Linux**: Claude credentials fall back to `~/.claude/.credentials.json`. All other providers work the same as macOS.

## Troubleshooting

**Gemini: `Token expired, refresh failed`**

`ai-usage` refreshes the Gemini token by reading the OAuth client ID/secret from the locally installed `gemini` CLI's `oauth2.js`. The resolver scans common install layouts (Homebrew, npm global, fnm/nvm, Nix) and transparently follows shell wrappers. If your install is in an unusual location, set:

```bash
export GEMINI_OAUTH_JS=/path/to/@google/gemini-cli-core/dist/src/code_assist/oauth2.js
```

**Claude: empty `plan` field**

The provider only fills `plan` when the OAuth `rateLimitTier` matches a known tier (`max`, `pro`, `team`, `enterprise`, `free`). Unknown internal tiers (e.g., `default_claude_ai`) are hidden rather than echoed verbatim.

## Requirements

- Python 3.10+
- Active credentials for the providers you want to query

---

## 中文说明

终端查询 AI 编程工具配额用量。支持 Claude Code、Codex、Gemini、GitHub Copilot、z.ai、OpenCode Go。

### 安装

```bash
pipx install ai-usage-cli
```

### 使用

```bash
ai-usage                      # 查看所有已启用的 Provider
ai-usage -p claude             # 只看 Claude
ai-usage -p claude codex       # 看 Claude 和 Codex
ai-usage -p opencode-go        # 只看 OpenCode Go
ai-usage -a                    # 包含未启用的 Provider
ai-usage --json                # JSON 输出（适合脚本处理）
ai-usage --plain               # 纯文本输出（无颜色、无 Unicode）
```

## Related Projects

- [CodexBar](https://github.com/steipete/CodexBar) — macOS menu bar app for AI coding tool usage tracking. `ai-usage-cli` shares the same `~/.codexbar/config.json` configuration and was built as a cross-platform CLI companion.

## License

[MIT](LICENSE)
