from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.text import Text

if TYPE_CHECKING:
    from .providers.base import RateWindow, UsageResult


# ── Rich (TTY) ──────────────────────────────────────────────

def _bar(used_pct: float, width: int = 20) -> Text:
    filled = int(used_pct / 100 * width)
    filled = max(0, min(width, filled))
    empty = width - filled

    if used_pct < 50:
        color = "green"
    elif used_pct < 80:
        color = "yellow"
    else:
        color = "red"

    bar = Text()
    bar.append("[")
    bar.append("\u2588" * filled, style=color)
    bar.append("\u2591" * empty, style="dim")
    bar.append("]")
    return bar


def _format_usage(used_pct: float) -> Text:
    remaining = 100 - used_pct
    t = Text()

    if used_pct >= 100:
        t.append("EXHAUSTED", style="bold red")
    elif used_pct >= 80:
        t.append(f"{remaining:5.1f}% left", style="bold red")
    elif used_pct >= 50:
        t.append(f"{remaining:5.1f}% left", style="yellow")
    elif used_pct > 0:
        t.append(f"{remaining:5.1f}% left", style="green")
    else:
        t.append("unused", style="green")

    return t


def render_text(results: list[UsageResult], console: Console) -> None:
    console.print()

    for r in results:
        header = Text()
        header.append(f"  {r.provider}", style="bold white")
        if r.source:
            header.append(f"  ({r.source})", style="dim")
        if r.plan:
            header.append(f"  [{r.plan}]", style="cyan")
        if r.email:
            header.append(f"  {r.email}", style="dim")
        console.print(header)

        if r.error:
            console.print(f"    Error: {r.error}", style="dim red")
            console.print()
            continue

        if not r.windows:
            console.print("    No usage data", style="dim")
            console.print()
            continue

        for w in r.windows:
            line = Text()
            line.append(f"    {w.label:<20} ")
            line.append_text(_format_usage(w.used_percent))
            line.append("  ")
            line.append_text(_bar(w.used_percent))
            if w.resets_at:
                line.append(f"  resets in {w.resets_at}", style="dim")
            console.print(line)

        if r.cost:
            cost_line = Text("    cost: ", style="dim")
            cost_line.append(f"${r.cost.used:.2f}", style="yellow")
            if r.cost.limit:
                cost_line.append(f" / ${r.cost.limit:.2f}", style="dim")
            cost_line.append(f" ({r.cost.period})", style="dim")
            console.print(cost_line)

        console.print()

    console.print()


# ── Plain (stdout / pipe) ───────────────────────────────────

def _plain_bar(used_pct: float, width: int = 20) -> str:
    filled = int(used_pct / 100 * width)
    filled = max(0, min(width, filled))
    empty = width - filled
    return "[" + "#" * filled + "-" * empty + "]"


def _plain_status(used_pct: float) -> str:
    if used_pct >= 100:
        return "EXHAUSTED"
    elif used_pct > 0:
        return f"{100 - used_pct:.1f}% left"
    else:
        return "unused"


def render_plain(results: list[UsageResult]) -> None:
    w = sys.stdout.write

    for r in results:
        parts = [r.provider]
        if r.source:
            parts.append(f"({r.source})")
        if r.plan:
            parts.append(f"[{r.plan}]")
        if r.email:
            parts.append(r.email)
        w(" ".join(parts) + "\n")

        if r.error:
            w(f"  ERROR: {r.error}\n\n")
            continue

        if not r.windows:
            w("  no data\n\n")
            continue

        for win in r.windows:
            status = _plain_status(win.used_percent)
            bar = _plain_bar(win.used_percent)
            reset = f"  resets in {win.resets_at}" if win.resets_at else ""
            w(f"  {win.label:<20} {status:<14} {bar}{reset}\n")

        if r.cost:
            cost = f"${r.cost.used:.2f}"
            if r.cost.limit:
                cost += f" / ${r.cost.limit:.2f}"
            w(f"  cost: {cost} ({r.cost.period})\n")

        w("\n")


# ── JSON ────────────────────────────────────────────────────

def render_json(results: list[UsageResult], console: Console) -> None:
    output = []
    for r in results:
        entry: dict = {"provider": r.provider, "source": r.source}
        if r.error:
            entry["error"] = r.error
        else:
            entry["plan"] = r.plan
            entry["email"] = r.email
            entry["windows"] = [
                {
                    "label": w.label,
                    "used_percent": w.used_percent,
                    "remaining_percent": round(100 - w.used_percent, 1),
                    "resets_at": w.resets_at,
                }
                for w in r.windows
            ]
            if r.cost:
                entry["cost"] = {
                    "used": r.cost.used,
                    "limit": r.cost.limit,
                    "currency": r.cost.currency,
                    "period": r.cost.period,
                }
        output.append(entry)
    console.print_json(json.dumps(output, ensure_ascii=False))
