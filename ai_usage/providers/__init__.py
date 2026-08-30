from .claude import ClaudeProvider
from .codex import CodexProvider
from .gemini import GeminiProvider
from .copilot import CopilotProvider
from .zai import ZaiProvider
from .opencode_go import OpenCodeGoProvider

ALL_PROVIDERS = [
    ClaudeProvider,
    CodexProvider,
    GeminiProvider,
    CopilotProvider,
    ZaiProvider,
    OpenCodeGoProvider,
]
