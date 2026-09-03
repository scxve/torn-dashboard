#!/usr/bin/env python3
"""Torn City desk dashboard for an 800x480 Raspberry Pi display."""

from __future__ import annotations

import os
import json
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


API_URL = "https://api.torn.com/v2/user"
SELECTIONS = "basic,bars,cooldowns,money,travel,networth,notifications"
# The Linux virtual console used by the Pi display supports the standard ANSI
# palette, not reliable 24-bit RGB. Named ANSI colours stay distinct on tty1.
GREEN = "bright_green"
DIM_GREEN = "green"
AMBER = "bright_yellow"
RED = "bright_red"
BLUE = "bright_blue"
YELLOW = "bright_yellow"
GREY = "bright_black"
WHITE = "white"

RESOURCE_COLOURS = {
    "LIFE": BLUE,
    "ENERGY": GREEN,
    "NERVE": RED,
    "HAPPY": YELLOW,
}


class TornAPIError(RuntimeError):
    pass


@dataclass
class DashboardState:
    data: dict[str, Any] = field(default_factory=dict)
    last_sync: datetime | None = None
    error: str | None = None
    consecutive_errors: int = 0


def deep_get(data: dict[str, Any], *path: str, default: Any = 0) -> Any:
    value: Any = data
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def format_duration(seconds: int | float | None, ready: str = "READY") -> str:
    seconds = max(0, int(seconds or 0))
    if seconds == 0:
        return ready
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days}d {hours:02}:{minutes:02}"
    return f"{hours:02}:{minutes:02}:{secs:02}"


def time_until(timestamp: int | float | None) -> str:
    """Format a Unix expiry timestamp as a live countdown."""
    if not timestamp:
        return "READY"
    return format_duration(max(0, int(timestamp) - int(time.time())))


def live_countdown(seconds_at_sync: int | float | None, elapsed: int) -> int:
    """Advance an API countdown locally between cached API responses."""
    return max(0, int(seconds_at_sync or 0) - max(0, elapsed))


def compact_number(value: int | float | None, money: bool = False) -> str:
    # Never let an unexpected/null API field take down the whole display.
    number = float(value or 0) if isinstance(value, (int, float)) else 0.0
    absolute = abs(number)
    suffix = ""
    divisor = 1.0
    for threshold, label in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if absolute >= threshold:
            divisor, suffix = threshold, label
            break
    if suffix:
        rendered = f"{number / divisor:.2f}".rstrip("0").rstrip(".") + suffix
    else:
        rendered = f"{int(number):,}"
    return f"${rendered}" if money else rendered


def load_env_file(path: str = ".env") -> None:
    """Load simple KEY=VALUE entries without requiring python-dotenv."""
    try:
        with open(path, encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    except FileNotFoundError:
        pass


def fetch_torn_data(api_key: str, timeout: float = 8.0) -> dict[str, Any]:
    query = urlencode({"selections": SELECTIONS, "comment": "pi-dash"})
    request = Request(
        f"{API_URL}?{query}",
        headers={
            "Authorization": f"ApiKey {api_key}",
            "User-Agent": "Pi-Torn-Desk-Dashboard/1.0",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            message = deep_get(payload, "error", "error", default=exc.reason)
        except (ValueError, UnicodeDecodeError):
            message = exc.reason
        raise TornAPIError(f"HTTP {exc.code}: {message}") from exc
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise TornAPIError("Invalid response from Torn API") from exc
    if "error" in payload:
        error = payload["error"]
        if isinstance(error, dict):
            raise TornAPIError(str(error.get("error") or error.get("code") or error))
        raise TornAPIError(str(error))
    return payload


def resource_panel(label: str, resource: dict[str, Any]) -> Panel:
    current = int(resource.get("current", 0) or 0)
    maximum = int(resource.get("maximum", 0) or 0)
    width = 14
    filled = round(width * min(1.0, current / maximum)) if maximum else 0
    if current > 0 and maximum > 0:
        filled = max(1, filled)
    colour = RESOURCE_COLOURS[label]
    title = Text()
    title.append(f"{label}  ", style=f"bold {WHITE}")
    title.append(f"{current:,}/{maximum:,}", style=f"bold {colour}")
    meter = Text("━" * filled, style=f"bold {colour}")
    meter.append("━" * (width - filled), style="black")
    return Panel(
        Group(title, meter),
        border_style=GREY,
        padding=(0, 1),
    )


def key_value_panel(title: str, rows: list[tuple[str, str, str]]) -> Panel:
    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column(style=WHITE, ratio=1)
    table.add_column(justify="right", ratio=1)
    for label, value, colour in rows:
        table.add_row(label, Text(value, style=f"bold {colour}"))
    return Panel(
        table,
        title=Text(title, style=f"bold {GREEN}"),
        title_align="center",
        border_style=GREY,
        padding=(0, 1),
    )


def build_dashboard(state: DashboardState, refresh_seconds: int) -> Layout:
    data = state.data
    profile = data.get("profile", {})
    bars = data.get("bars", {})
    cooldowns = data.get("cooldowns", {})
    money = data.get("money", {})
    networth = data.get("networth", {})
    travel = data.get("travel", {})
    notifications = data.get("notifications", {})
    chain = bars.get("chain") or {}
    elapsed = 0
    if state.last_sync:
        elapsed = max(0, int((datetime.now().astimezone() - state.last_sync).total_seconds()))

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="bars", size=5),
        Layout(name="middle", ratio=1),
        Layout(name="next", size=3),
        Layout(name="footer", size=3),
    )

    clock = datetime.now().astimezone().strftime("%H:%M:%S")
    name = str(profile.get("name", "CONNECTING")).upper()
    player_id = profile.get("id", "----")
    api_style = GREEN if not state.error else AMBER if state.data else RED
    api_label = "API OK" if not state.error else "STALE" if state.data else "API ERROR"
    header = Table.grid(expand=True)
    header.add_column(ratio=1)
    header.add_column(ratio=1, justify="center")
    header.add_column(ratio=1, justify="right")
    header.add_row(
        Text("TORN // LIVE OPS", style=f"bold {GREEN}"),
        Text(f"{name} [{player_id}]", style=f"bold {GREEN}"),
        Text.assemble((clock, f"bold {WHITE}"), (f"  {api_label}", f"bold {api_style}")),
    )
    layout["header"].update(Panel(header, border_style=GREY, padding=(0, 1)))

    bar_grid = Table.grid(expand=True, padding=(0, 0))
    for _ in range(4):
        bar_grid.add_column(ratio=1)
    bar_grid.add_row(
        resource_panel("LIFE", bars.get("life", {})),
        resource_panel("ENERGY", bars.get("energy", {})),
        resource_panel("NERVE", bars.get("nerve", {})),
        resource_panel("HAPPY", bars.get("happy", {})),
    )
    layout["bars"].update(bar_grid)

    layout["middle"].split_row(Layout(name="left"), Layout(name="right"))
    layout["left"].split_column(Layout(name="player", size=8), Layout(name="funds"))
    layout["right"].split_column(Layout(name="operations", size=11), Layout(name="alerts"))
    status = profile.get("status", {})
    status_value = str(status.get("description") or status.get("state") or "Unknown")
    status_colour = GREEN if status.get("state", "Okay") == "Okay" else AMBER
    life_full = live_countdown(deep_get(bars, "life", "full_time", default=0), elapsed)
    happy_full = live_countdown(deep_get(bars, "happy", "full_time", default=0), elapsed)
    city_bank = money.get("city_bank") or {}
    faction_balance = money.get("faction") or {}
    faction_cash = faction_balance.get("money", 0) if isinstance(faction_balance, dict) else faction_balance
    player_rows = [
        ("LEVEL", str(profile.get("level", "--")), WHITE),
        ("STATUS", status_value[:24], status_colour),
        ("CASH", compact_number(money.get("wallet"), money=True), WHITE),
        ("POINTS", compact_number(money.get("points")), WHITE),
        ("NETWORTH", compact_number(networth.get("total"), money=True), WHITE),
    ]
    layout["player"].update(key_value_panel("PLAYER", player_rows))

    funds_rows = [
        ("CITY BANK", compact_number(city_bank.get("amount"), money=True), WHITE),
        ("BANK ENDS", time_until(city_bank.get("until")), AMBER if city_bank.get("until") else GREY),
        ("VAULT", compact_number(money.get("vault"), money=True), WHITE),
        ("FACTION CASH", compact_number(faction_cash, money=True), WHITE),
        ("DAILY NW", compact_number(money.get("daily_networth"), money=True), WHITE),
        ("LIFE FULL", format_duration(life_full), GREEN if not life_full else AMBER),
        ("HAPPY FULL", format_duration(happy_full), GREEN if not happy_full else AMBER),
    ]
    layout["funds"].update(key_value_panel("FUNDS + RECOVERY", funds_rows))

    drug_cd = live_countdown(cooldowns.get("drug"), elapsed)
    booster_cd = live_countdown(cooldowns.get("booster"), elapsed)
    medical_cd = live_countdown(cooldowns.get("medical"), elapsed)
    travel_left = live_countdown(travel.get("time_left"), elapsed)
    if travel_left > 0:
        travel_value = f"{travel.get('destination', 'Abroad')} {format_duration(travel_left)}"
    else:
        destination = str(travel.get("destination", "Torn"))
        travel_value = "In Torn" if destination.lower() == "torn" else destination

    chain_current = int(chain.get("current", 0) or 0)
    chain_max = int(chain.get("max", 0) or 0)
    chain_value = f"{chain_current:,} / {chain_max:,}" if chain else "INACTIVE"
    chain_cooldown = time_until(chain.get("cooldown"))
    operations_rows = [
        ("CHAIN", chain_value, WHITE if chain else GREY),
        ("CHAIN TIMER", format_duration(live_countdown(chain.get("timeout"), elapsed)), AMBER if chain else GREY),
        ("CHAIN CD", chain_cooldown, AMBER if chain.get("cooldown") else GREY),
        ("DRUG CD", format_duration(drug_cd), AMBER if drug_cd else GREEN),
        ("BOOSTER CD", format_duration(booster_cd), AMBER if booster_cd else GREEN),
        ("MEDICAL CD", format_duration(medical_cd), AMBER if medical_cd else GREEN),
        ("TRAVEL", travel_value[:24], WHITE),
    ]
    layout["operations"].update(key_value_panel("OPERATIONS", operations_rows))

    alerts_rows = [
        ("MESSAGES", str(notifications.get("messages", 0)), AMBER if notifications.get("messages") else GREY),
        ("EVENTS", str(notifications.get("events", 0)), AMBER if notifications.get("events") else GREY),
        ("AWARDS", str(notifications.get("awards", 0)), AMBER if notifications.get("awards") else GREY),
        ("COMPETITION", str(notifications.get("competition", 0)), AMBER if notifications.get("competition") else GREY),
    ]
    layout["alerts"].update(key_value_panel("ALERTS", alerts_rows))

    energy_full = live_countdown(deep_get(bars, "energy", "full_time", default=0), elapsed)
    nerve_full = live_countdown(deep_get(bars, "nerve", "full_time", default=0), elapsed)
    next_line = Text(justify="center")
    next_line.append("NEXT: ", style=f"bold {GREEN}")
    next_line.append(f"ENERGY FULL {format_duration(energy_full)}", style=WHITE)
    next_line.append("  │  ", style=GREY)
    next_line.append(f"NERVE FULL {format_duration(nerve_full)}", style=WHITE)
    next_line.append("  │  ", style=GREY)
    next_line.append(f"DRUG READY {format_duration(drug_cd)}", style=WHITE)
    layout["next"].update(Panel(Align.center(next_line), border_style=GREY, padding=(0, 1)))

    sync = state.last_sync.astimezone().strftime("%H:%M:%S") if state.last_sync else "--:--:--"
    footer_text = Text(justify="center")
    footer_text.append(f"API {refresh_seconds}s", style=WHITE)
    footer_text.append("  •  ", style=DIM_GREEN)
    footer_text.append("TIMERS 1s", style=WHITE)
    footer_text.append("  •  ", style=DIM_GREEN)
    footer_text.append(f"LAST SYNC {sync}", style=WHITE)
    if state.error:
        footer_text.append("  •  ", style=DIM_GREEN)
        footer_text.append(state.error[:42], style=AMBER)
    layout["footer"].update(Panel(footer_text, border_style=GREY, padding=(0, 1)))
    return layout


def main() -> int:
    load_env_file()
    api_key = os.getenv("TORN_API_KEY", "").strip()
    # Torn commonly serves these selections from a roughly 30-second cache.
    # Poll at that cadence and animate countdowns locally every second.
    refresh_seconds = max(30, int(os.getenv("REFRESH_SECONDS", "30")))
    if not api_key:
        print("TORN_API_KEY is missing. Copy .env.example to .env and add your key.", file=sys.stderr)
        return 2

    console = Console(highlight=False, color_system="standard")
    state = DashboardState()
    running = True

    def stop(_signum: int, _frame: Any) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    next_fetch = 0.0
    with Live(build_dashboard(state, refresh_seconds), console=console, screen=True, refresh_per_second=1) as live:
        while running:
            now = time.monotonic()
            if now >= next_fetch:
                try:
                    state.data = fetch_torn_data(api_key)
                    state.last_sync = datetime.now().astimezone()
                    state.error = None
                    state.consecutive_errors = 0
                    next_fetch = now + refresh_seconds
                except (URLError, TimeoutError, OSError, TornAPIError) as exc:
                    state.consecutive_errors += 1
                    state.error = str(exc)
                    backoff = min(60, refresh_seconds * (2 ** min(state.consecutive_errors - 1, 3)))
                    next_fetch = now + backoff
            live.update(build_dashboard(state, refresh_seconds))
            time.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
