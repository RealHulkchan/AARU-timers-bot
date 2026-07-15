"""
ArcheAge Timers — Discord bot
Same weekly/daily event schedule and boss-timer logic as the desktop widget
(archeage_translator_easy_v2.py), reimplemented standalone so it doesn't pull in
tkinter/EasyOCR/torch. Posts one embed per configured channel and edits it in
place every 15s (like a BDO-style boss-timer bot) instead of spamming messages.

Setup:
    pip install -r requirements_bot.txt
    set DISCORD_TOKEN=your-bot-token   (or put it in a .env file, see .env.example)
    python discord_bot.py

Commands (all slash commands):
    /setup                          - post the live timer board in this channel
    /timer start name hours         - start a custom countdown (guild boss etc.)
    /timer list                     - list running custom timers
    /timer cancel name              - cancel a running custom timer
    /events                         - one-off snapshot (ephemeral)
"""

import os
import json
import asyncio
from datetime import datetime, timedelta, timezone
from collections import namedtuple

import discord
from discord import app_commands
from discord.ext import tasks

# ── Schedule data (mirrors archeage_translator_easy_v2.py) ──────────────────────
MOSCOW = timezone(timedelta(hours=3))

WEEKLY_SCHEDULE = {
    0: [("kraken", "\U0001F419", "Kraken", ["19:30"]),
        ("charybdis", "\U0001F41B", "Charybdis (Kalidis)", ["20:30"]),
        ("garden_anthalon", "\U0001F47A", "Garden Anthalon", ["21:30"]),
        ("golden_plains", "\U0001F3DF", "Golden Plains Battle", ["19:00~20:00"])],
    1: [("abyssal_attack", "\U0001F30A", "Abyssal Attack", ["15:00", "21:00"]),
        ("black_dragon", "\U0001F409", "Black Dragon", ["19:30"]),
        ("leviathan", "\U0001F40A", "Leviathan", ["20:30"]),
        ("fesanix", "\U0001F9DA", "Fesanix (Inter-Server PVP)", ["21:30"]),
        ("golden_plains", "\U0001F3DF", "Golden Plains Battle", ["16:00~17:00", "22:30~23:59"])],
    2: [("castle_siege", "\U0001F3F0", "Castle Siege", ["21:00"]),
        ("golden_plains", "\U0001F3DF", "Golden Plains Battle", ["19:00~20:00"])],
    3: [("abyssal_attack", "\U0001F30A", "Abyssal Attack", ["15:00", "21:00"]),
        ("kraken", "\U0001F419", "Kraken", ["19:30"]),
        ("leviathan", "\U0001F40A", "Leviathan", ["20:30"]),
        ("golden_plains", "\U0001F3DF", "Golden Plains Battle", ["16:00~17:00", "22:30~23:59"])],
    4: [("black_dragon", "\U0001F409", "Black Dragon", ["19:30"]),
        ("charybdis", "\U0001F41B", "Charybdis (Kalidis)", ["20:30"]),
        ("garden_anthalon", "\U0001F47A", "Garden Anthalon", ["21:30"]),
        ("invasion", "\U0001F6E1", "Invasion", ["22:00"]),
        ("golden_plains", "\U0001F3DF", "Golden Plains Battle", ["19:00~20:00"])],
    5: [("abyssal_attack", "\U0001F30A", "Abyssal Attack", ["15:00", "21:00"]),
        ("invasion", "\U0001F6E1", "Invasion", ["16:00"]),
        ("prairie", "\U0001F304", "Prairie", ["18:00"]),
        ("kraken", "\U0001F419", "Kraken", ["19:30"]),
        ("charybdis", "\U0001F41B", "Charybdis (Kalidis)", ["20:30"]),
        ("golden_plains", "\U0001F3DF", "Golden Plains Battle", ["16:00~17:00", "22:30~23:59"])],
    6: [("prairie", "\U0001F304", "Prairie", ["18:00"]),
        ("fesanix", "\U0001F9DA", "Fesanix (Inter-Server PVP)", ["18:50"]),
        ("black_dragon", "\U0001F409", "Black Dragon", ["19:30"]),
        ("garden_anthalon", "\U0001F47A", "Garden Anthalon", ["19:50"]),
        ("leviathan", "\U0001F40A", "Leviathan", ["20:30"]),
        ("golden_plains", "\U0001F3DF", "Golden Plains Battle", ["19:00~20:00"])],
}

DAILY_TIMED_EVENTS = [
    ("daily_reset", "\U0001F504", "Daily Reset", ["00:00"]),
    ("skyfin", "\U0001F4CD", "Skyfin Base Capture",
     ["14:30~15:15", "17:00~18:00", "21:00~21:45"]),
    ("red_dragon_keep", "\U0001F432", "Red Dragon's Keep",
     ["13:20~14:00", "18:20~19:00", "21:20~22:00"]),
    ("kadum", "\U0001F479", "Kadum",
     ["12:40~13:20", "17:40~18:20", "20:40~21:20"]),
    ("hiram_city", "\U0001F3DB", "The Fall of Hiram City",
     ["00:40~01:20", "12:00~12:40", "17:00~17:40", "20:00~20:40"]),
]


def _ingame_occurrences(ingame_hour):
    base = ((ingame_hour - 10) % 24) * 10
    return sorted(f"{((base + i*240) % 1440)//60:02d}:{((base + i*240) % 1440)%60:02d}"
                  for i in range(6))


DAILY_INGAME_EVENTS = [
    ("jmg", "\U00002694", "JMG", 6),
    ("normal_cr", "\U0001F3C6", "Normal CR", 12),
    ("sgcr", "\U0001F947", "SGCR", 18),
    ("hiram_rift", "\U0001F300", "Hiram Rift", 21),
    ("gr", "\U0001F480", "GR", 0),
]

EventOcc = namedtuple("EventOcc", "key icon name time_str dt end")

# Primary = weekly bosses/sieges (highest priority, own section on the board).
# Secondary = everything clock-driven (CR/GR/SGCR/Hiram Rift/Red Dragon/Skyfin/
# Kadum/Hiram City/Daily Reset) — same events, just a lower-priority section.
PRIMARY_KEYS = frozenset(key for day in WEEKLY_SCHEDULE.values() for key, *_ in day)


def _parse_span(d, t):
    start_s, _, end_s = t.partition("~")
    hh, mm = map(int, start_s.split(":"))
    dt = datetime(d.year, d.month, d.day, hh, mm, tzinfo=MOSCOW)
    end = None
    if end_s:
        eh, em = map(int, end_s.split(":"))
        end = datetime(d.year, d.month, d.day, eh, em, tzinfo=MOSCOW)
        if end <= dt:
            end += timedelta(days=1)
    return start_s, dt, end


def _occurrences_for_date(d, disabled=()):
    out = []
    day = d.weekday()
    for key, icon, name, times in (list(WEEKLY_SCHEDULE.get(day, []))
                                   + list(DAILY_TIMED_EVENTS)):
        if key in disabled:
            continue
        for t in times:
            ts, dt, end = _parse_span(d, t)
            out.append(EventOcc(key, icon, name, ts, dt, end))
    for key, icon, name, hour in DAILY_INGAME_EVENTS:
        if key in disabled:
            continue
        disp = f"{name} (in-game {hour:02d}:00)"
        for t in _ingame_occurrences(hour):
            hh, mm = map(int, t.split(":"))
            out.append(EventOcc(key, icon, disp, t,
                                datetime(d.year, d.month, d.day, hh, mm, tzinfo=MOSCOW),
                                None))
    return sorted(out, key=lambda o: o.dt)


def active_occurrences(now, disabled=()):
    out = [occ for occ in _occurrences_for_date(now.date(), disabled)
           if occ.end is not None and occ.dt <= now < occ.end]
    return sorted(out, key=lambda o: o.end)


def upcoming_occurrences(now, count=8, disabled=(), horizon_days=3):
    out = []
    d = now.date()
    for _ in range(horizon_days):
        for occ in _occurrences_for_date(d, disabled):
            if occ.dt >= now:
                out.append(occ)
                if len(out) >= count:
                    return out
        d += timedelta(days=1)
    return out


def fmt_rem(secs):
    secs = max(0, int(secs))
    h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
    if h:
        return f"{h}h {m:02d}m"
    if m >= 5:
        return f"{m}m"
    return f"{m}m {s:02d}s"


def dur_label(h):
    m = int(round(h * 60))
    hh, mm = divmod(m, 60)
    if not hh:
        return f"{mm}m"
    if not mm:
        return f"{hh}h"
    return f"{hh}h {mm:02d}m"


# ── Persistence (per-guild board channel/message + custom timers) ──────────────
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_timers.json")


def load_data():
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_data(data):
    try:
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[SAVE] failed: {e}")


guild_data = load_data()   # {guild_id_str: {"channel_id", "message_id", "custom_timers":[{"name","end"}]}}


def gd(guild_id):
    return guild_data.setdefault(str(guild_id), {"channel_id": None, "message_id": None,
                                                   "custom_timers": []})


# ── Embed builder ────────────────────────────────────────────────────────────────
# Built as one big markdown description (not embed fields) so section headers can
# use "##" (renders large/bold) and rows get a full blank line of breathing room —
# fields force a cramped fixed layout that can't do either.
EMBED_COLOR = 0xC8A96E
UPCOMING_PER_SECTION = 6


def _live_line(occ, now):
    rem = max(0, int((occ.end - now).total_seconds()))
    return f"{occ.icon} **{occ.name}** — {fmt_rem(rem)} left"


def _upcoming_line(occ, now):
    secs = max(0, int((occ.dt - now).total_seconds()))
    local_t = occ.dt.astimezone(timezone.utc).strftime("%H:%M UTC")
    return f"{occ.icon} **{occ.name}** — {local_t} · in {fmt_rem(secs)}"


def build_embed(entry):
    now = datetime.now(MOSCOW)

    custom_lines = []
    for t in entry["custom_timers"]:
        rem = t["end"] - now.timestamp()
        custom_lines.append(f"⏱ **{t['name']}** — UP!" if rem <= 0
                             else f"⏱ **{t['name']}** — {fmt_rem(rem)} left")

    active = active_occurrences(now)
    active_primary   = [o for o in active if o.key in PRIMARY_KEYS]
    active_secondary = [o for o in active if o.key not in PRIMARY_KEYS]

    occs = upcoming_occurrences(now, count=40)
    up_primary   = [o for o in occs if o.key in PRIMARY_KEYS][:UPCOMING_PER_SECTION]
    up_secondary = [o for o in occs if o.key not in PRIMARY_KEYS][:UPCOMING_PER_SECTION]

    parts = [f"Server (MSK) `{now:%H:%M:%S}`"]

    if custom_lines:
        parts.append("## ⏱️ Custom Timers\n" + "\n\n".join(custom_lines))

    if active_primary or up_primary:
        section = ["## ⚔️ Bosses & Sieges"]
        if active_primary:
            section.append("**Live now**\n" + "\n\n".join(_live_line(o, now) for o in active_primary))
        if up_primary:
            section.append("**Upcoming**\n" + "\n\n".join(_upcoming_line(o, now) for o in up_primary))
        parts.append("\n".join(section))

    if active_secondary or up_secondary:
        section = ["## 🕐 Daily Cycles"]
        if active_secondary:
            section.append("**Live now**\n" + "\n\n".join(_live_line(o, now) for o in active_secondary))
        if up_secondary:
            section.append("**Upcoming**\n" + "\n\n".join(_upcoming_line(o, now) for o in up_secondary))
        parts.append("\n".join(section))

    embed = discord.Embed(title="🗓️ ArcheAge Timers", description="\n\n".join(parts),
                           color=EMBED_COLOR, timestamp=datetime.now(timezone.utc))
    embed.set_footer(text="Updates every 15s")
    return embed


# ── Bot ──────────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()


class TimersBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        refresh_loop.start()


client = TimersBot()


@client.event
async def on_ready():
    print(f"[READY] logged in as {client.user}")


@tasks.loop(seconds=15)
async def refresh_loop():
    expired_any = False
    for guild_id, entry in list(guild_data.items()):
        now_ts = datetime.now(MOSCOW).timestamp()
        before = len(entry["custom_timers"])
        entry["custom_timers"] = [t for t in entry["custom_timers"]
                                   if now_ts - t["end"] <= 300]   # keep "UP!" 5 min
        if len(entry["custom_timers"]) != before:
            expired_any = True

        if not entry.get("channel_id"):
            continue

        def _unbind(reason):
            print(f"[TICK] guild {guild_id}: {reason} — unbinding (run /setup again to re-enable)")
            entry["channel_id"] = None
            entry["message_id"] = None
            save_data(guild_data)

        channel = client.get_channel(entry["channel_id"])
        if channel is None:
            try:
                channel = await client.fetch_channel(entry["channel_id"])
            except (discord.NotFound, discord.Forbidden):
                _unbind("board channel was deleted or is no longer accessible")
                continue
            except Exception as e:
                print(f"[TICK] guild {guild_id}: channel fetch failed: {e}")
                continue

        embed = build_embed(entry)
        try:
            if entry.get("message_id"):
                msg = await channel.fetch_message(entry["message_id"])
                await msg.edit(embed=embed)
            else:
                msg = await channel.send(embed=embed)
                entry["message_id"] = msg.id
                save_data(guild_data)
        except discord.NotFound:
            # Someone deleted the board message by hand — stop chasing it instead
            # of silently respawning a new one every 15s; /setup rebinds cleanly.
            _unbind("board message was deleted")
        except discord.Forbidden:
            _unbind("lost permission to post in the board channel")
        except Exception as e:
            print(f"[TICK] guild {guild_id} failed: {e}")
    if expired_any:
        save_data(guild_data)


@refresh_loop.before_loop
async def before_refresh():
    await client.wait_until_ready()


# ── Slash commands ───────────────────────────────────────────────────────────────
@client.tree.command(name="setup", description="Post the live ArcheAge timer board in this channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_cmd(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    embed = build_embed(entry)
    msg = await interaction.channel.send(embed=embed)
    entry["channel_id"] = interaction.channel_id
    entry["message_id"] = msg.id
    save_data(guild_data)
    await interaction.response.send_message("Timer board posted — it'll update every 15s.",
                                             ephemeral=True)


timer_group = app_commands.Group(name="timer", description="Custom countdown timers (guild boss respawns etc.)")


@timer_group.command(name="start", description="Start a custom countdown timer")
@app_commands.describe(name="Timer name (e.g. Kraken)", hours="Duration in hours (e.g. 2 or 1.5)")
async def timer_start(interaction: discord.Interaction, name: str, hours: float):
    if hours <= 0 or hours > 72:
        await interaction.response.send_message("Hours must be between 0 and 72.", ephemeral=True)
        return
    entry = gd(interaction.guild_id)
    name = name.strip()[:24] or "timer"
    end = datetime.now(MOSCOW).timestamp() + hours * 3600
    entry["custom_timers"].append({"name": name, "end": end})
    entry["custom_timers"].sort(key=lambda t: t["end"])
    save_data(guild_data)
    # Ephemeral (only you see this) so it doesn't leave a permanent message behind —
    # the timer itself shows up under Custom Timers on the live board within 15s.
    await interaction.response.send_message(
        f"Timer started: **{name}** — {dur_label(hours)} ({fmt_rem(hours * 3600)} left). "
        "It'll appear on the live board within 15s.", ephemeral=True)


@timer_group.command(name="list", description="List running custom timers")
async def timer_list(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    if not entry["custom_timers"]:
        await interaction.response.send_message("No custom timers running.", ephemeral=True)
        return
    now_ts = datetime.now(MOSCOW).timestamp()
    lines = [f"⏱ **{t['name']}** — {fmt_rem(t['end'] - now_ts)} left"
             for t in entry["custom_timers"]]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@timer_group.command(name="cancel", description="Cancel a running custom timer")
@app_commands.describe(name="Name of the timer to cancel")
async def timer_cancel(interaction: discord.Interaction, name: str):
    entry = gd(interaction.guild_id)
    before = len(entry["custom_timers"])
    entry["custom_timers"] = [t for t in entry["custom_timers"] if t["name"] != name]
    if len(entry["custom_timers"]) == before:
        await interaction.response.send_message(f"No timer named **{name}**.", ephemeral=True)
        return
    save_data(guild_data)
    await interaction.response.send_message(f"Cancelled **{name}**.", ephemeral=True)


@timer_cancel.autocomplete("name")
async def timer_cancel_autocomplete(interaction: discord.Interaction, current: str):
    entry = gd(interaction.guild_id)
    return [app_commands.Choice(name=t["name"], value=t["name"])
            for t in entry["custom_timers"] if current.lower() in t["name"].lower()][:25]


client.tree.add_command(timer_group)


@client.tree.command(name="events", description="One-off snapshot of live/upcoming events")
async def events_cmd(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    embed = build_embed(entry)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── Entrypoint ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN environment variable is not set.")
    client.run(token)
