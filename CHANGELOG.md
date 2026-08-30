# Changelog

## 0.2.0 - 2026-08-30

### Features

- Add an independent OpenCode Go quota provider backed by the official rolling, weekly, and monthly usage API.
- Support OpenCode's XDG credential store and `OPENCODE_AUTH_CONTENT`, while honoring CodexBar's `opencodego` enablement setting.

### Fixes

- Read Gemini quota data from the current `buckets` response field while retaining the legacy fallback.
- Keep the OpenCode Go and Codex quota sources separate so consumers cannot use the wrong window as an execution gate.

### Documentation

- Document the `opencode-go` CLI selector, credential source, and independent quota semantics.
