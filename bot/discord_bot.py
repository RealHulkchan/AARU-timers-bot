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
    /setup                           - post the live timer board in this channel
    /timer start name hours          - start a custom countdown (guild boss etc.)
    /timer list                      - list running custom timers
    /timer cancel name               - cancel a running custom timer
    /roles set target role           - ping `role` 15m before Guild Boss/JMG/Morpheus/Rangora starts
    /roles clear target              - stop pinging for that target
    /roles list                      - show configured ping roles
    /roles message                   - post a permanent self-assign button message for the 4 roles
    /events                          - one-off snapshot (ephemeral, auto-dismisses)
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

# Primary = bosses/PVP (highest priority, own section on the board): every weekly
# boss/siege plus JMG (also a boss, just on the 4h in-game-clock cycle).
# Secondary = the remaining clock-driven dailies (GR/SGCR/Hiram Rift/Red Dragon/
# Skyfin/Kadum/Hiram City/Daily Reset) — same events, lower-priority section.
PRIMARY_KEYS = frozenset(key for day in WEEKLY_SCHEDULE.values() for key, *_ in day) | {"jmg"}


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
# DATA_DIR should point at a mounted Railway Volume in production — the container's
# own filesystem is wiped on every redeploy, which would otherwise lose the board
# binding and any running custom timers on every push. Falls back to the script's
# own folder for local runs.
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(DATA_DIR, "bot_timers.json")


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


guild_data = load_data()   # {guild_id_str: {"channel_id", "message_id", "custom_timers":[{"name","end","pinged"}],
                            #                 "ping_roles": {target_key: role_id}, "pinged_occ": {target_key: occ_id}}}


def gd(guild_id):
    """Fetch (or create) a guild's entry, back-filling any keys older saved data
    is missing — setdefault at the guild_data level alone won't add new keys to
    an entry that already existed on disk before a feature was added."""
    entry = guild_data.setdefault(str(guild_id), {})
    entry.setdefault("channel_id", None)
    entry.setdefault("message_id", None)
    entry.setdefault("custom_timers", [])
    entry.setdefault("ping_roles", {})
    entry.setdefault("pinged_occ", {})
    return entry


# Targets that can have a ping role configured. Custom-timer targets are matched
# by the timer's name (case-insensitive) — this covers both the preset buttons and
# /timer start when someone types one of these names. JMG is matched against the
# schedule instead, since it's not a custom timer.
PING_TARGETS = [("guild_boss", "Guild Boss"), ("jmg", "JMG"),
                ("morpheus", "Morpheus"), ("rangora", "Rangora")]
PING_LABELS = dict(PING_TARGETS)
NAME_TO_PING_KEY = {label.lower(): key for key, label in PING_TARGETS if key != "jmg"}


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


def _dedupe_next(occs):
    """Keep only the soonest occurrence of each repeating event (occs is already
    chronological, so the first one seen per key is the next one)."""
    seen, out = set(), []
    for o in occs:
        if o.key not in seen:
            seen.add(o.key)
            out.append(o)
    return out


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

    occs = upcoming_occurrences(now, count=60)
    up_primary   = _dedupe_next(o for o in occs if o.key in PRIMARY_KEYS)[:UPCOMING_PER_SECTION]
    up_secondary = _dedupe_next(o for o in occs if o.key not in PRIMARY_KEYS)[:UPCOMING_PER_SECTION]

    parts = [f"Server (MSK) `{now:%H:%M:%S}`"]

    if custom_lines:
        parts.append("## ⏱️ Custom Timers\n" + "\n\n".join(custom_lines))

    if active_primary or up_primary:
        section = ["## ⚔️ Bosses & PVP"]
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


async def _reply_dismiss(interaction: discord.Interaction, content: str = None, *,
                          embed: discord.Embed = None, delay: float = 120):
    """Ephemeral reply that deletes itself after `delay` seconds (Discord has no
    native auto-expiry for ephemeral messages, so the bot has to clean up after itself)."""
    await interaction.response.send_message(content=content, embed=embed, ephemeral=True)

    async def _later():
        await asyncio.sleep(delay)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
    asyncio.create_task(_later())


# One-click preset timers shown as buttons under the board (mirrors the desktop
# widget's _TIMER_PRESETS). Fixed custom_ids + timeout=None so the buttons keep
# working after a bot restart, as long as the view is re-registered in setup_hook.
TIMER_PRESETS = [("Guild Boss", 2.0), ("Morpheus", 12.0), ("Rangora", 12.0)]


class PresetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _start(self, interaction, name, hours):
        entry = gd(interaction.guild_id)
        now_ts = datetime.now(MOSCOW).timestamp()
        # Guards against double-clicks/retries spawning two of the same preset timer
        # at once — each would independently trigger its own duplicate ping.
        existing = next((t for t in entry["custom_timers"]
                          if t["name"] == name and t["end"] > now_ts), None)
        if existing:
            await _reply_dismiss(interaction, f"**{name}** is already running — "
                                  f"{fmt_rem(existing['end'] - now_ts)} left.")
            return
        end = now_ts + hours * 3600
        entry["custom_timers"].append({"name": name, "end": end})
        entry["custom_timers"].sort(key=lambda t: t["end"])
        save_data(guild_data)
        await _reply_dismiss(
            interaction,
            f"Timer started: **{name}** — {dur_label(hours)}. It'll appear on the "
            "board within 15s.")

    @discord.ui.button(label="+ Guild Boss", style=discord.ButtonStyle.secondary,
                        custom_id="preset_guild_boss")
    async def add_guild_boss(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._start(interaction, "Guild Boss", 2.0)

    @discord.ui.button(label="+ Morph", style=discord.ButtonStyle.secondary,
                        custom_id="preset_morph")
    async def add_morph(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._start(interaction, "Morpheus", 12.0)

    @discord.ui.button(label="+ Rangora", style=discord.ButtonStyle.secondary,
                        custom_id="preset_rangora")
    async def add_rangora(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._start(interaction, "Rangora", 12.0)


def build_role_embed():
    """Boxed (embed, not plain text) opt-in message so it visually matches the
    board instead of looking like a loose announcement."""
    embed = discord.Embed(
        title="🔔 Opt Into Timer Pings",
        description=("Click a button to get **or remove** a role — you'll be pinged "
                      "15 minutes before that timer starts.\n\n"
                      "*An admin binds each button to a role with `/roles set`.*"),
        color=EMBED_COLOR)
    return embed


# Self-assign buttons for the four ping-role targets (posted once via /roles message,
# stays forever). Toggles whatever role is currently bound via /roles set — no
# re-post needed if the role binding changes later.
class RoleButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _toggle(self, interaction: discord.Interaction, key: str):
        label = PING_LABELS[key]
        entry = gd(interaction.guild_id)
        role_id = entry["ping_roles"].get(key)
        if not role_id:
            await _reply_dismiss(interaction, f"No role is bound to **{label}** yet — "
                                  f"an admin needs to run `/roles set`.")
            return
        role = interaction.guild.get_role(role_id)
        if role is None:
            await _reply_dismiss(interaction, f"The role bound to **{label}** no longer exists.")
            return
        member = interaction.user
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Self-unassigned via timer role button")
                await _reply_dismiss(interaction, f"Removed {role.mention} — no more **{label}** pings.")
            else:
                await member.add_roles(role, reason="Self-assigned via timer role button")
                await _reply_dismiss(interaction, f"Gave you {role.mention} — you'll be pinged "
                                      f"15 minutes before **{label}** starts.")
        except discord.Forbidden:
            await _reply_dismiss(interaction, "I can't manage that role — check I have "
                                  "**Manage Roles** and my role is positioned above it.")
        except Exception as e:
            await _reply_dismiss(interaction, f"Failed: {e}")

    @discord.ui.button(label="JMG", style=discord.ButtonStyle.secondary, custom_id="role_jmg")
    async def jmg_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "jmg")

    @discord.ui.button(label="Rangora", style=discord.ButtonStyle.secondary, custom_id="role_rangora")
    async def rangora_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "rangora")

    @discord.ui.button(label="Morpheus", style=discord.ButtonStyle.secondary, custom_id="role_morpheus")
    async def morpheus_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "morpheus")

    @discord.ui.button(label="Guild Boss", style=discord.ButtonStyle.secondary, custom_id="role_guild_boss")
    async def guild_boss_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "guild_boss")


# ── Bot ──────────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()


class TimersBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.add_view(PresetView())      # re-register so buttons work on old messages after a restart
        self.add_view(RoleButtonView())
        try:
            synced = await self.tree.sync()
            print(f"[SYNC] {len(synced)} global commands: {[c.name for c in synced]}")
        except Exception as e:
            print(f"[SYNC] FAILED: {e!r}")
        refresh_loop.start()


client = TimersBot()


@client.event
async def on_ready():
    print(f"[READY] logged in as {client.user}")


PING_WINDOW_SECS = 15 * 60


async def _check_pings(guild_id, entry, channel, now_ts):
    """Ping the configured role once, 15 minutes before a Guild Boss/Morpheus/
    Rangora custom timer starts, or JMG's next occurrence starts."""
    ping_roles = entry["ping_roles"]
    if not ping_roles:
        return

    for t in entry["custom_timers"]:
        key = NAME_TO_PING_KEY.get(t["name"].strip().lower())
        role_id = key and ping_roles.get(key)
        rem = t["end"] - now_ts
        if role_id and not t.get("pinged") and 0 < rem <= PING_WINDOW_SECS:
            # Marked pinged BEFORE the send (not after) so there's no await window
            # where a re-entrant check could see "not yet pinged" and fire twice —
            # at most one send per timer even if something calls in unexpectedly.
            t["pinged"] = True
            save_data(guild_data)
            await _send_ping(channel, role_id, PING_LABELS[key], rem)

    jmg_role = ping_roles.get("jmg")
    if jmg_role:
        now_dt = datetime.now(MOSCOW)
        upcoming_jmg = next((o for o in upcoming_occurrences(now_dt, count=10) if o.key == "jmg"), None)
        if upcoming_jmg:
            rem = (upcoming_jmg.dt - now_dt).total_seconds()
            occ_id = upcoming_jmg.dt.isoformat()
            if entry["pinged_occ"].get("jmg") != occ_id and 0 < rem <= PING_WINDOW_SECS:
                entry["pinged_occ"]["jmg"] = occ_id
                save_data(guild_data)
                await _send_ping(channel, jmg_role, "JMG", rem)


async def _send_ping(channel, role_id, label, rem_secs):
    try:
        await channel.send(f"<@&{role_id}> **{label}** in {fmt_rem(rem_secs)}!",
                            allowed_mentions=discord.AllowedMentions(roles=True))
        return True
    except Exception as e:
        print(f"[PING] {label} failed: {e}")
        return False


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

        await _check_pings(guild_id, entry, channel, now_ts)

        embed = build_embed(entry)
        try:
            if entry.get("message_id"):
                msg = await channel.fetch_message(entry["message_id"])
                await msg.edit(embed=embed)
            else:
                msg = await channel.send(embed=embed, view=PresetView())
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
    # Posted first so it lands above the board (Discord orders by send time).
    await interaction.channel.send(embed=build_role_embed(), view=RoleButtonView())
    embed = build_embed(entry)
    msg = await interaction.channel.send(embed=embed, view=PresetView())
    entry["channel_id"] = interaction.channel_id
    entry["message_id"] = msg.id
    save_data(guild_data)
    await _reply_dismiss(interaction, "Timer board posted — it'll update every 15s.")


timer_group = app_commands.Group(name="timer", description="Custom countdown timers (guild boss respawns etc.)")


@timer_group.command(name="start", description="Start a custom countdown timer")
@app_commands.describe(name="Timer name (e.g. Kraken)", hours="Duration in hours (e.g. 2 or 1.5)")
async def timer_start(interaction: discord.Interaction, name: str, hours: float):
    if hours <= 0 or hours > 72:
        await _reply_dismiss(interaction, "Hours must be between 0 and 72.")
        return
    entry = gd(interaction.guild_id)
    name = name.strip()[:24] or "timer"
    end = datetime.now(MOSCOW).timestamp() + hours * 3600
    entry["custom_timers"].append({"name": name, "end": end})
    entry["custom_timers"].sort(key=lambda t: t["end"])
    save_data(guild_data)
    # Ephemeral (only you see this) so it doesn't leave a permanent message behind —
    # the timer itself shows up under Custom Timers on the live board within 15s.
    await _reply_dismiss(
        interaction,
        f"Timer started: **{name}** — {dur_label(hours)} ({fmt_rem(hours * 3600)} left). "
        "It'll appear on the live board within 15s.")


@timer_group.command(name="list", description="List running custom timers")
async def timer_list(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    if not entry["custom_timers"]:
        await _reply_dismiss(interaction, "No custom timers running.")
        return
    now_ts = datetime.now(MOSCOW).timestamp()
    lines = [f"⏱ **{t['name']}** — {fmt_rem(t['end'] - now_ts)} left"
             for t in entry["custom_timers"]]
    await _reply_dismiss(interaction, "\n".join(lines))


@timer_group.command(name="cancel", description="Cancel a running custom timer")
@app_commands.describe(name="Name of the timer to cancel")
async def timer_cancel(interaction: discord.Interaction, name: str):
    entry = gd(interaction.guild_id)
    before = len(entry["custom_timers"])
    entry["custom_timers"] = [t for t in entry["custom_timers"] if t["name"] != name]
    if len(entry["custom_timers"]) == before:
        await _reply_dismiss(interaction, f"No timer named **{name}**.")
        return
    save_data(guild_data)
    await _reply_dismiss(interaction, f"Cancelled **{name}**.")


@timer_cancel.autocomplete("name")
async def timer_cancel_autocomplete(interaction: discord.Interaction, current: str):
    entry = gd(interaction.guild_id)
    return [app_commands.Choice(name=t["name"], value=t["name"])
            for t in entry["custom_timers"] if current.lower() in t["name"].lower()][:25]


client.tree.add_command(timer_group)


roles_group = app_commands.Group(name="roles", description="Configure which role gets pinged 15m before a timer starts")


@roles_group.command(name="set", description="Ping a role 15 minutes before this timer starts")
@app_commands.describe(target="Which timer/event", role="Role to ping")
@app_commands.choices(target=[app_commands.Choice(name=label, value=key) for key, label in PING_TARGETS])
@app_commands.checks.has_permissions(manage_guild=True)
async def roles_set(interaction: discord.Interaction, target: app_commands.Choice[str], role: discord.Role):
    entry = gd(interaction.guild_id)
    entry["ping_roles"][target.value] = role.id
    save_data(guild_data)
    await _reply_dismiss(interaction, f"**{target.name}** will now ping {role.mention} 15 minutes before it starts.")


@roles_group.command(name="clear", description="Stop pinging a role for this timer")
@app_commands.describe(target="Which timer/event")
@app_commands.choices(target=[app_commands.Choice(name=label, value=key) for key, label in PING_TARGETS])
@app_commands.checks.has_permissions(manage_guild=True)
async def roles_clear(interaction: discord.Interaction, target: app_commands.Choice[str]):
    entry = gd(interaction.guild_id)
    had = entry["ping_roles"].pop(target.value, None) is not None
    save_data(guild_data)
    await _reply_dismiss(interaction, f"Cleared the ping role for **{target.name}**."
                          if had else f"**{target.name}** had no ping role set.")


@roles_group.command(name="list", description="Show configured ping roles")
async def roles_list(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    lines = [f"**{label}** — " + (f"<@&{entry['ping_roles'][key]}>" if key in entry["ping_roles"] else "not set")
             for key, label in PING_TARGETS]
    await _reply_dismiss(interaction, "\n".join(lines))


@roles_group.command(name="message", description="Post a permanent self-assign button message for the four ping roles")
@app_commands.checks.has_permissions(manage_guild=True)
async def roles_message(interaction: discord.Interaction):
    await interaction.channel.send(embed=build_role_embed(), view=RoleButtonView())
    await _reply_dismiss(interaction, "Posted.")


client.tree.add_command(roles_group)


@client.tree.command(name="events", description="One-off snapshot of live/upcoming events")
async def events_cmd(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    embed = build_embed(entry)
    await _reply_dismiss(interaction, embed=embed)


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
