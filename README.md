# ai-usage-cli

[![PyPI version](https://img.shields.io/pypi/v/ai-usage-cli)](https://pypi.org/project/ai-usage-cli/)
[![Python](https://img.shields.io/pypi/pyversions/ai-usage-cli)](https://pypi.org/project/ai-usage-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Check your AI coding tool usage quotas from the terminal. Supports **Claude Code**, **Codex**, **Gemini**, **GitHub Copilot**, and **z.ai**.

```
$ ai-usage

  Claude  (keychain)  [Max]  user@example.com
    Daily (5h window)   剩余 72.0%  [█████░░░░░░░░░░░░░░░]  4h 12m 后重置

  Codex  (oauth)  [Plus]
    Daily              剩余 95.2%  [█░░░░░░░░░░░░░░░░░░░]

  Gemini  (oauth)  [Free]
    Per-minute         剩余 100.0% [░░░░░░░░░░░░░░░░░░░░]
    Daily              剩余 88.4%  [██░░░░░░░░░░░░░░░░░░]  16h 后重置
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

## Configuration

Provider settings are stored in `~/.codexbar/config.json`. Each provider can be enabled/disabled and configured with API keys where needed.

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

## Requirements

- Python 3.10+
- Active credentials for the providers you want to query

---

## 中文说明

终端查询 AI 编程工具配额用量。支持 Claude Code、Codex、Gemini、GitHub Copilot、z.ai。

### 安装

```bash
pipx install ai-usage-cli
```

### 使用

```bash
ai-usage                      # 查看所有已启用的 Provider
ai-usage -p claude             # 只看 Claude
ai-usage -p claude codex       # 看 Claude 和 Codex
ai-usage -a                    # 包含未启用的 Provider
ai-usage --json                # JSON 输出（适合脚本处理）
ai-usage --plain               # 纯文本输出（无颜色、无 Unicode）
```

## License

[MIT](LICENSE)
