from .agy import AgyProvider
from .claude import ClaudeProvider
from .codex import CodexProvider
from .gemini import GeminiProvider
from .copilot import CopilotProvider
from .zai import ZaiProvider

ALL_PROVIDERS = [
    AgyProvider,
    ClaudeProvider,
    CodexProvider,
    GeminiProvider,
    CopilotProvider,
    ZaiProvider,
]
