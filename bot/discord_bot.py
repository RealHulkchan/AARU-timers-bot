"""
ArcheAge Timers — Discord bot
Same weekly/daily event schedule and boss-timer logic as the desktop widget
(archeage_translator_easy_v2.py), reimplemented standalone so it doesn't pull in
tkinter/EasyOCR/torch. Posts one embed per configured channel and edits it in
place every 5s (like a BDO-style boss-timer bot) instead of spamming messages.

Setup:
    pip install -r requirements_bot.txt
    set DISCORD_TOKEN=your-bot-token   (or put it in a .env file, see .env.example)
    python discord_bot.py

Commands (all slash commands):
    /setup                           - post the live timer board in this channel
    /timer start name hours          - start a custom countdown (guild boss etc.)
    /timer list                      - list running custom timers
    /timer cancel name               - cancel a running custom timer
    /roles set target role           - ping `role` before Guild Boss/JMG/Morpheus/Rangora/Skyfin/Halcy/
                                        Tokens starts (15m+5m), or Prairie/Invasion starts (30m+5m)
    /roles clear target              - stop pinging for that target
    /roles list                      - show configured ping roles
    /roles message                   - post a permanent self-assign button message for the 4 roles
    /language set|show               - toggle the board/pings between English and Russian
    /names set key language text     - set this server's own name for an event/boss in a language
    /names clear key language        - reset an event/boss's name back to default
    /names list                      - show every event/boss's name in both languages
    /events                          - one-off snapshot (ephemeral, auto-dismisses)
    /clear                           - delete this bot's own messages in the channel
    /permissions set target level    - set the permission level a command/button needs on this server
    /permissions clear target        - reset a command/button's level back to default
    /permissions list                - show every command/button's current level
    /buttons hide button             - hide a preset/role button on this server (repost to apply)
    /buttons show button             - un-hide it
    /buttons list                    - show which buttons are hidden here

Permission levels are per-guild and configurable — see /permissions above.
Defaults: preset buttons = everyone; everything else (/setup, /timer,
/roles, /language set, /names set|clear, /clear) = Manage Messages.
/permissions itself always requires Manage Server, hardcoded, so it can't
be used to lower its own bar.
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
# boss/siege plus JMG (also a boss, just on the 4h in-game-clock cycle), minus
# Abyssal Attack which moved to the Upcoming Events section below.
# Secondary/"Upcoming Events" = everything else (GR/SGCR/Hiram Rift/Red Dragon/
# Skyfin/Kadum/Daily Reset/Abyssal Attack).
PRIMARY_KEYS = (frozenset(key for day in WEEKLY_SCHEDULE.values() for key, *_ in day)
                | {"jmg"}) - {"abyssal_attack"}


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


guild_data = load_data()   # {guild_id_str: {"channel_id", "message_id",
                            #                 "custom_timers":[{"name","end","pinged_15m","pinged_5m"}],
                            #                 "ping_roles": {target_key: role_id},
                            #                 "pinged_occ_15m": {"jmg": occ_id}, "pinged_occ_5m": {"jmg": occ_id}}}


def gd(guild_id):
    """Fetch (or create) a guild's entry, back-filling any keys older saved data
    is missing — setdefault at the guild_data level alone won't add new keys to
    an entry that already existed on disk before a feature was added."""
    entry = guild_data.setdefault(str(guild_id), {})
    entry.setdefault("channel_id", None)
    entry.setdefault("message_id", None)
    entry.setdefault("custom_timers", [])
    entry.setdefault("ping_roles", {})
    entry.setdefault("pinged_occ_15m", {})
    entry.setdefault("pinged_occ_5m", {})
    entry.setdefault("pinged_occ_30m", {})   # Prairie/Invasion use 30m+5m instead of 15m+5m
    entry.setdefault("language", "en")
    entry.setdefault("event_names", {})   # {event_key: {"en": "...", "ru": "..."}}
    entry.setdefault("permissions", {})   # {target: "everyone"|"manage_messages"|"manage_server"}
    entry.setdefault("hidden_buttons", [])   # list of button custom_ids not shown on this guild's messages
    return entry


# Per-guild-overridable permission levels for admin-facing commands/buttons.
# "everyone" = no restriction, "manage_messages"/"manage_server" = that Discord
# permission required. Defaults here match this server's current setup; any
# guild can override any target independently via /permissions set.
PERMISSION_TARGETS = [
    ("preset_timers", "+ Guild Boss/Morph/Rangora buttons"),
    ("timer", "/timer start, list, cancel"),
    ("setup", "/setup"),
    ("roles", "/roles set, clear, message"),
    ("language", "/language set"),
    ("names", "/names set, clear"),
    ("clear_cmd", "/clear"),
    ("buttons", "/buttons hide, show"),
]
PERMISSION_TARGET_DESCRIPTIONS = {
    "preset_timers": "The buttons under the board that start a preset Guild Boss "
                      "(2h), Morpheus (12h), or Rangora (12h) countdown with one click.",
    "timer": "/timer start — start any custom countdown under any name/duration. "
             "/timer list — see what's running. /timer cancel — stop one.",
    "setup": "Posts (or moves) the live timer board and the self-assign role "
              "message into the current channel. Doesn't delete an existing board "
              "elsewhere — use /clear for that.",
    "roles": "/roles set — bind a Discord role to ping 15m and 5m before a timer/"
             "event starts. /roles clear — unbind one. /roles message — repost "
             "just the self-assign role buttons without touching the board.",
    "language": "/language set — switches the board, pings, and button labels "
                "between English and Russian for this server.",
    "names": "/names set — give an event/boss its own name in a language (e.g. "
             "a nickname like \"Halcy\"). /names clear — reset one back to default.",
    "clear_cmd": "Deletes this bot's own messages in the current channel (old "
                 "board posts, ping alerts, leftover confirmations) — never "
                 "other users' messages.",
    "buttons": "/buttons hide/show — controls which individual preset/role "
               "buttons appear on this server's board and role message.",
}
DEFAULT_PERMISSION_LEVELS = {
    "preset_timers": "everyone",
    "timer": "manage_messages",
    "setup": "manage_messages",
    "roles": "manage_messages",
    "language": "manage_messages",
    "names": "manage_messages",
    "clear_cmd": "manage_messages",
    "buttons": "manage_messages",
}
PERMISSION_LEVEL_LABELS = {"everyone": "Everyone", "manage_messages": "Manage Messages",
                            "manage_server": "Manage Server"}


def _permission_level(entry, target):
    return entry["permissions"].get(target, DEFAULT_PERMISSION_LEVELS[target])


def _has_permission_level(member: discord.Member, level: str) -> bool:
    if level == "everyone":
        return True
    if level == "manage_messages":
        return member.guild_permissions.manage_messages
    if level == "manage_server":
        return member.guild_permissions.manage_guild
    return False


def require_permission(target):
    """App-command check that reads the guild's configured level for `target`
    (falling back to its default) instead of a level fixed at decoration time —
    this is what makes /permissions set actually change enforcement per guild."""
    async def predicate(interaction: discord.Interaction) -> bool:
        entry = gd(interaction.guild_id)
        level = _permission_level(entry, target)
        if _has_permission_level(interaction.user, level):
            return True
        raise app_commands.CheckFailure(
            f"`[403 Forbidden]` This requires the **{PERMISSION_LEVEL_LABELS[level]}** "
            "permission on this server.")
    return app_commands.check(predicate)


# refresh_loop iterates guild_data entries directly (not through gd()), so a guild
# persisted before a feature added new keys would never get them backfilled and
# crash the loop with a KeyError the first time it ran post-deploy. Force every
# already-saved guild through gd() once at startup so this can't happen again.
for _gid in list(guild_data.keys()):
    gd(_gid)


# Targets that can have a ping role configured. Custom-timer targets are matched
# by the timer's name (case-insensitive) — this covers both the preset buttons and
# /timer start when someone types one of these names. Schedule targets (fixed
# in-game timing, not a manually-started timer) are matched against the schedule
# by event key instead. "Halcy" is this server's name for Golden Plains Battle,
# so it aliases to the existing "golden_plains" schedule key rather than needing
# its own schedule entry.
PING_TARGETS = [("guild_boss", "Guild Boss"), ("jmg", "JMG"),
                ("morpheus", "Morpheus"), ("rangora", "Rangora"),
                ("skyfin", "Skyfin"), ("halcy", "Halcy"),
                ("prairie", "Prairie"), ("invasion", "Invasion"),
                ("tokens", "Tokens")]
PING_LABELS = dict(PING_TARGETS)
SCHEDULE_PING_KEYS = {"jmg", "skyfin", "halcy", "prairie", "invasion"}
SCHEDULE_KEY_ALIAS = {"halcy": "golden_plains"}   # ping target key -> actual schedule event key
NAME_TO_PING_KEY = {label.lower(): key for key, label in PING_TARGETS
                     if key not in SCHEDULE_PING_KEYS}


# ── Localization ─────────────────────────────────────────────────────────────────
# Every event/boss name is admin-editable per language via /names set — these are
# just the defaults. English defaults are pulled straight from the schedule data
# (one source of truth for spelling) plus the four custom-timer/ping-only targets.
# DEFAULT_NAMES_RU is a provided community translation (not guessed) covering the
# weekly bosses/sieges, the fixed daily events, most in-game-clock dailies, and
# two of the four ping-only targets; /names set still overrides either on a
# per-guild basis, and still covers anything not listed here (Normal CR, and the
# morpheus/halcy ping-only targets, have no built-in Russian name yet).
def _collect_default_names():
    names = {}
    for day in WEEKLY_SCHEDULE.values():
        for key, icon, name, _times in day:
            names.setdefault(key, name)
    for key, icon, name, _times in DAILY_TIMED_EVENTS:
        names.setdefault(key, name)
    for key, icon, name, _hour in DAILY_INGAME_EVENTS:
        names.setdefault(key, name)
    return names


DEFAULT_NAMES = _collect_default_names()
DEFAULT_NAMES.update({"guild_boss": "Guild Boss", "morpheus": "Morpheus",
                       "rangora": "Rangora", "halcy": "Halcy", "tokens": "Tokens"})

DEFAULT_NAMES_RU = {
    "kraken": "Кракен",
    "charybdis": "Калидис",
    "garden_anthalon": "Анталон (Сады Матери)",
    "golden_plains": "Битва за Даскшир",
    "abyssal_attack": "Око Бури",
    "black_dragon": "Ксанатос",
    "leviathan": "Левиафан",
    "fesanix": "Фесаникс (Пепельные равнины)",
    "castle_siege": "Осада замка",
    "invasion": "Оборона Ифнира",
    "prairie": "Великий Луг",
    "daily_reset": "Ресеты",
    "skyfin": "Битва за Зачарованные пруды",
    "red_dragon_keep": "Логово дракона (Гартарейн)",
    "kadum": "Ущелье кровавой росы (Гардум)",
    "jmg": "АГЛ",
    "sgcr": "Кровавый разлом (Анталон)",
    "hiram_rift": "Фантомы",
    "gr": "Призрачный разлом",
    "rangora": "Марли",
    "guild_boss": "Ги босса",
}

# Static board/UI chrome — these ARE translated up front (ordinary interface text,
# not guild-specific game slang, so no need to defer to an admin command).
UI = {
    "en": {
        "title": "🗓️ ArcheAge Timers",
        "server_label": "Server (MSK)",
        "custom_timers": "⏱️ Guild Timers",
        "bosses_pvp": "⚔️ Bosses & PVP",
        "daily_cycles": "🕐 Upcoming Events",
        "live_now": "**Live now**",
        "upcoming": "**Upcoming**",
        "footer": "Updates every 5s",
        "opt_in_title": "🔔 Opt Into Timer Pings",
        "opt_in_desc": ("Click a button to get **or remove** a role — you'll be pinged "
                         "15 and 5 minutes before that timer starts (30 and 5 for "
                         "Prairie/Invasion).\n\n"
                         "*An admin binds each button to a role with `/roles set`.*"),
    },
    "ru": {
        "title": "🗓️ Таймеры ArcheAge",
        "server_label": "Сервер (МСК)",
        "custom_timers": "⏱️ Гильдейские таймеры",
        "bosses_pvp": "⚔️ Боссы и PvP",
        "daily_cycles": "🕐 Ближайшие события",
        "live_now": "**Сейчас идёт**",
        "upcoming": "**Скоро**",
        "footer": "Обновляется каждые 5с",
        "opt_in_title": "🔔 Подписка на уведомления",
        "opt_in_desc": ("Нажмите кнопку, чтобы получить **или снять** роль — вам придёт "
                         "уведомление за 15 и за 5 минут до начала (за 30 и за 5 минут "
                         "для Prairie/Invasion).\n\n"
                         "*Админ привязывает роль к кнопке командой `/roles set`.*"),
    },
}


def ui(entry, key):
    return UI[entry.get("language", "en")][key]


def get_name(entry, key, fallback=None):
    """Localized display name for an event/boss key, in priority order: the
    guild's override for the current language, the built-in Russian default (if
    the guild is in RU and one exists), the guild's English override, the
    built-in English default, else the caller-supplied fallback (e.g. a raw
    custom-timer name that isn't one of the known translatable keys)."""
    lang = entry.get("language", "en")
    overrides = entry["event_names"].get(key, {})
    if overrides.get(lang):
        return overrides[lang]
    if lang == "ru" and key in DEFAULT_NAMES_RU:
        return DEFAULT_NAMES_RU[key]
    if overrides.get("en"):
        return overrides["en"]
    return DEFAULT_NAMES.get(key, fallback if fallback is not None else key)


def localized_occ_name(entry, occ):
    """occ.name may carry an "(in-game HH:00)" suffix baked in by
    _occurrences_for_date — translate the base name and re-append it."""
    base, sep, suffix = occ.name.partition(" (in-game ")
    return get_name(entry, occ.key, base) + (sep + suffix if sep else "")


# ── Embed builder ────────────────────────────────────────────────────────────────
# Built as one big markdown description (not embed fields) so section headers can
# use "##" (renders large/bold) and rows get a full blank line of breathing room —
# fields force a cramped fixed layout that can't do either.
EMBED_COLOR = 0xC8A96E
UPCOMING_PER_SECTION = 6


def _live_line(entry, occ, now):
    rem = max(0, int((occ.end - now).total_seconds()))
    # Shows when it ENDS (local tag + MSK), matching Upcoming's local+MSK+count
    # format instead of a bare countdown.
    epoch = int(occ.end.timestamp())
    msk_t = occ.end.strftime("%H:%M")
    return (f"{occ.icon} **{localized_occ_name(entry, occ)}** — <t:{epoch}:t> "
            f"· MSK {msk_t} · {fmt_rem(rem)} left")


def _upcoming_line(entry, occ, now):
    secs = max(0, int((occ.dt - now).total_seconds()))
    # <t:epoch:t> is a Discord timestamp tag — it renders in each viewer's own
    # local time/locale automatically, no per-user config needed. MSK stays
    # alongside it since that's the server's actual clock.
    epoch = int(occ.dt.timestamp())
    msk_t = occ.dt.strftime("%H:%M")
    return (f"{occ.icon} **{localized_occ_name(entry, occ)}** — <t:{epoch}:t> "
            f"· MSK {msk_t} · in {fmt_rem(secs)}")


def _dedupe_next(occs):
    """Keep only the soonest occurrence of each repeating event (occs is already
    chronological, so the first one seen per key is the next one)."""
    seen, out = set(), []
    for o in occs:
        if o.key not in seen:
            seen.add(o.key)
            out.append(o)
    return out


def _custom_timer_name(entry, t):
    """A custom timer's display name is translatable if it matches one of the
    known preset/ping targets (Guild Boss/Morpheus/Rangora); otherwise it's an
    arbitrary name someone typed via /timer start and is shown as-is."""
    key = NAME_TO_PING_KEY.get(t["name"].strip().lower())
    return get_name(entry, key, t["name"]) if key else t["name"]


def build_embed(entry):
    now = datetime.now(MOSCOW)

    custom_lines = []
    for t in entry["custom_timers"]:
        rem = t["end"] - now.timestamp()
        name = _custom_timer_name(entry, t)
        if rem <= 0:
            custom_lines.append(f"⏱ **{name}** — UP!")
        else:
            epoch = int(t["end"])
            msk_t = datetime.fromtimestamp(t["end"], tz=MOSCOW).strftime("%H:%M")
            custom_lines.append(f"⏱ **{name}** — <t:{epoch}:t> · MSK {msk_t} · {fmt_rem(rem)} left")

    active = active_occurrences(now)
    active_primary   = [o for o in active if o.key in PRIMARY_KEYS]
    active_secondary = [o for o in active if o.key not in PRIMARY_KEYS]
    active_primary_keys   = {o.key for o in active_primary}
    active_secondary_keys = {o.key for o in active_secondary}

    # An event already shown under Live Now is excluded from Upcoming — otherwise
    # its NEXT occurrence (the one after the one currently running) shows up there
    # too, which reads as if it's about to happen again imminently.
    occs = upcoming_occurrences(now, count=60)
    up_primary   = _dedupe_next(o for o in occs if o.key in PRIMARY_KEYS
                                 and o.key not in active_primary_keys)[:UPCOMING_PER_SECTION]
    up_secondary = _dedupe_next(o for o in occs if o.key not in PRIMARY_KEYS
                                 and o.key not in active_secondary_keys)[:UPCOMING_PER_SECTION]

    parts = [f"# {ui(entry, 'title')} — {ui(entry, 'server_label')} `{now:%H:%M:%S}`"]

    if custom_lines:
        parts.append(f"## {ui(entry, 'custom_timers')}\n" + "\n\n".join(custom_lines))

    if active_primary or up_primary:
        section = [f"## {ui(entry, 'bosses_pvp')}"]
        if active_primary:
            section.append(ui(entry, "live_now") + "\n" +
                            "\n\n".join(_live_line(entry, o, now) for o in active_primary))
        if up_primary:
            section.append(ui(entry, "upcoming") + "\n" +
                            "\n\n".join(_upcoming_line(entry, o, now) for o in up_primary))
        parts.append("\n".join(section))

    if active_secondary or up_secondary:
        section = [f"## {ui(entry, 'daily_cycles')}"]
        if active_secondary:
            section.append(ui(entry, "live_now") + "\n" +
                            "\n\n".join(_live_line(entry, o, now) for o in active_secondary))
        if up_secondary:
            section.append(ui(entry, "upcoming") + "\n" +
                            "\n\n".join(_upcoming_line(entry, o, now) for o in up_secondary))
        parts.append("\n".join(section))

    # Extra blank line between top-level sections (vs. the single blank line used
    # for spacing within a section) so the section break reads clearly on its own.
    embed = discord.Embed(description="\n\n\n".join(parts),
                           color=EMBED_COLOR, timestamp=datetime.now(timezone.utc))
    embed.set_footer(text=ui(entry, "footer"))
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


# One-click preset timers shown as buttons under the board. Fixed custom_ids +
# timeout=None so the buttons keep working after a bot restart, as long as the
# view is re-registered in setup_hook.
# The stored timer NAME is always the canonical English key text (it's how
# NAME_TO_PING_KEY matches it for pings/board display) — only the visible button
# LABEL and the confirmation message get translated. This is the whole point of
# the key/name split: renaming a boss via /names set can never break matching,
# because matching never looks at the display name, only at this fixed literal.
PRESET_BUTTON_KEYS = {"preset_guild_boss": "guild_boss", "preset_morph": "morpheus",
                       "preset_rangora": "rangora"}


class PresetView(discord.ui.View):
    def __init__(self, entry=None):
        super().__init__(timeout=None)
        entry = entry or {"language": "en", "event_names": {}, "hidden_buttons": []}
        hidden = entry.get("hidden_buttons", [])
        for child in list(self.children):
            custom_id = getattr(child, "custom_id", None)
            if custom_id in hidden:
                self.remove_item(child)
                continue
            key = PRESET_BUTTON_KEYS.get(custom_id)
            if key:
                child.label = f"+ {get_name(entry, key)}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Runs before any button in this view. Level is per-guild configurable
        via /permissions set target:preset_timers — defaults to "everyone".
        RoleButtonView (self-assign ping roles) is untouched and stays open."""
        entry = gd(interaction.guild_id)
        level = _permission_level(entry, "preset_timers")
        if _has_permission_level(interaction.user, level):
            return True
        await _reply_dismiss(interaction, f"`[403 Forbidden]` Starting a preset timer requires "
                              f"the **{PERMISSION_LEVEL_LABELS[level]}** permission.")
        return False

    async def _start(self, interaction, name, hours):
        entry = gd(interaction.guild_id)
        now_ts = datetime.now(MOSCOW).timestamp()
        # Guards against double-clicks/retries spawning two of the same preset timer
        # at once — each would independently trigger its own duplicate ping.
        existing = next((t for t in entry["custom_timers"]
                          if t["name"] == name and t["end"] > now_ts), None)
        display_name = _custom_timer_name(entry, {"name": name})
        if existing:
            await _reply_dismiss(interaction, f"**{display_name}** is already running — "
                                  f"{fmt_rem(existing['end'] - now_ts)} left.")
            return
        end = now_ts + hours * 3600
        entry["custom_timers"].append({"name": name, "end": end})
        entry["custom_timers"].sort(key=lambda t: t["end"])
        save_data(guild_data)
        await _reply_dismiss(
            interaction,
            f"Timer started: **{display_name}** — {dur_label(hours)}. It'll appear on the "
            "board within 5s.")

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


def build_role_embed(entry):
    """Boxed (embed, not plain text) opt-in message so it visually matches the
    board instead of looking like a loose announcement."""
    return discord.Embed(title=ui(entry, "opt_in_title"), description=ui(entry, "opt_in_desc"),
                          color=EMBED_COLOR)


ROLE_BUTTON_KEYS = {"role_jmg": "jmg", "role_rangora": "rangora", "role_morpheus": "morpheus",
                     "role_guild_boss": "guild_boss", "role_skyfin": "skyfin", "role_halcy": "halcy",
                     "role_prairie": "prairie", "role_invasion": "invasion", "role_tokens": "tokens"}


# Self-assign buttons for the ping-role targets (posted once via /roles message,
# stays forever). Toggles whatever role is currently bound via /roles set — no
# re-post needed if the role binding changes later.
class RoleButtonView(discord.ui.View):
    def __init__(self, entry=None):
        super().__init__(timeout=None)
        entry = entry or {"language": "en", "event_names": {}, "hidden_buttons": []}
        hidden = entry.get("hidden_buttons", [])
        for child in list(self.children):
            custom_id = getattr(child, "custom_id", None)
            if custom_id in hidden:
                self.remove_item(child)
                continue
            key = ROLE_BUTTON_KEYS.get(custom_id)
            if key:
                child.label = get_name(entry, key)

    async def _toggle(self, interaction: discord.Interaction, key: str):
        entry = gd(interaction.guild_id)
        label = get_name(entry, key)
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
                                      f"{_alert_timing_text(key)} before **{label}** starts.")
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

    @discord.ui.button(label="Skyfin", style=discord.ButtonStyle.secondary, custom_id="role_skyfin")
    async def skyfin_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "skyfin")

    @discord.ui.button(label="Halcy", style=discord.ButtonStyle.secondary, custom_id="role_halcy")
    async def halcy_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "halcy")

    @discord.ui.button(label="Prairie", style=discord.ButtonStyle.secondary, custom_id="role_prairie")
    async def prairie_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "prairie")

    @discord.ui.button(label="Invasion", style=discord.ButtonStyle.secondary, custom_id="role_invasion")
    async def invasion_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "invasion")

    @discord.ui.button(label="Tokens", style=discord.ButtonStyle.secondary, custom_id="role_tokens")
    async def tokens_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "tokens")


# Every hideable button, custom_id -> a static label for the /buttons command's
# choices (can't use get_name() here since choices are fixed at registration
# time, not per-invocation/per-language).
BUTTON_REGISTRY = (
    [(cid, f"Preset: + {DEFAULT_NAMES.get(key, key)}") for cid, key in PRESET_BUTTON_KEYS.items()]
    + [(cid, f"Role: {DEFAULT_NAMES.get(key, key)}") for cid, key in ROLE_BUTTON_KEYS.items()]
)


# ── Bot ──────────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()


class TimersBot(discord.Client):
    def __init__(self):
        # Without a cap, discord.py blocks a request indefinitely through
        # however many 429 retries it takes (this is what the repeating
        # "We are being rate limited... Retrying in Xs" warnings were —
        # the board-edit call sitting in a growing backoff loop). Capping it
        # means a congested board edit gives up quickly instead of occupying
        # request capacity that ping_loop's alerts need more urgently.
        super().__init__(intents=intents, max_ratelimit_timeout=8)
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
        ping_loop.start()


client = TimersBot()


@client.event
async def on_ready():
    print(f"[READY] logged in as {client.user}")


@client.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Without this, a failed permission check (or any other error) before the
    command body ever runs means the interaction is never responded to at all —
    Discord just shows "the application did not respond" with no explanation."""
    if isinstance(error, app_commands.MissingPermissions):
        perms = ", ".join(p.replace("_", " ").title() for p in error.missing_permissions)
        msg = f"`[403 Missing Permissions]` You need the **{perms}** permission to use this command."
    elif isinstance(error, app_commands.CheckFailure):
        # require_permission() raises CheckFailure with a specific message already
        # attached; fall back to a generic one for any other check failure.
        msg = str(error) or "`[403 Forbidden]` You don't have permission to use this command."
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"`[429 Cooldown]` Slow down — try again in {error.retry_after:.1f}s."
    else:
        print(f"[CMD ERROR] {interaction.command}: {error!r}")
        msg = "`[500 Command Error]` Something went wrong running that command."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


# Each alert tier is (window_secs, per-timer "already pinged" flag, per-JMG-occurrence
# tracking dict key, display label) — kept as separate flags/dicts so the 15m and
# 5m alerts fire independently instead of the second one being suppressed by the
# first's flag. The display label is the fixed tier name ("15m"/"5m"), NOT the
# actual remaining time at the moment the tick happened to land — even with
# ping_loop's 1s cadence that's never exactly e.g. 900.000s, so showing the raw
# number would read as a random/buggy value instead of the clean tier name.
# Custom-timer alerts (Guild Boss/Morpheus/Rangora/Tokens) always use these two
# tiers. Schedule-target alerts default to the same tiers too, EXCEPT Prairie
# and Invasion which use SCHEDULE_WINDOW_OVERRIDES (30m+5m) instead — per-target
# so any future one-off tier doesn't need touching every other target.
PING_WINDOWS = [
    (15 * 60, "pinged_15m", "pinged_occ_15m", "15m"),
    (5 * 60,  "pinged_5m",  "pinged_occ_5m",  "5m"),
]
SCHEDULE_DEFAULT_WINDOWS = [
    (15 * 60, "pinged_occ_15m", "15m"),
    (5 * 60,  "pinged_occ_5m",  "5m"),
]
SCHEDULE_WINDOW_OVERRIDES = {
    "prairie": [(30 * 60, "pinged_occ_30m", "30m"), (5 * 60, "pinged_occ_5m", "5m")],
    "invasion": [(30 * 60, "pinged_occ_30m", "30m"), (5 * 60, "pinged_occ_5m", "5m")],
}


def _alert_timing_text(key):
    """Human-readable tier labels for a target, e.g. '15m and 5m' or, for
    Prairie/Invasion, '30m and 5m' — used in confirmation messages so they
    don't hardcode the wrong tiers for a target with an override."""
    if key in SCHEDULE_PING_KEYS:
        windows = SCHEDULE_WINDOW_OVERRIDES.get(key, SCHEDULE_DEFAULT_WINDOWS)
        labels = [w[2] for w in windows]
    else:
        labels = [w[3] for w in PING_WINDOWS]
    return " and ".join(labels)


async def _check_pings(guild_id, entry, channel, now_ts):
    """Ping the configured role before a timer/event starts: 15m+5m for custom
    timers and most schedule targets, 30m+5m for Prairie/Invasion."""
    ping_roles = entry["ping_roles"]
    if not ping_roles:
        return

    for window_secs, flag, _occ_key, window_label in PING_WINDOWS:
        for t in entry["custom_timers"]:
            key = NAME_TO_PING_KEY.get(t["name"].strip().lower())
            role_id = key and ping_roles.get(key)
            rem = t["end"] - now_ts
            if role_id and not t.get(flag) and 0 < rem <= window_secs:
                # Marked pinged BEFORE the send (not after) so there's no await
                # window where a re-entrant check could fire twice.
                t[flag] = True
                save_data(guild_data)
                await _send_ping(channel, role_id, get_name(entry, key), window_label)

    now_dt = datetime.now(MOSCOW)
    # count=60 so a schedule target isn't missed just because other events fill
    # the first few nearer-term slots.
    occs = upcoming_occurrences(now_dt, count=60)

    for sched_key in SCHEDULE_PING_KEYS:
        role_id = ping_roles.get(sched_key)
        if not role_id:
            continue
        actual_key = SCHEDULE_KEY_ALIAS.get(sched_key, sched_key)
        occ = next((o for o in occs if o.key == actual_key), None)
        if occ is None:
            continue
        rem = (occ.dt - now_dt).total_seconds()
        occ_id = occ.dt.isoformat()
        for window_secs, occ_dict_key, window_label in SCHEDULE_WINDOW_OVERRIDES.get(
                sched_key, SCHEDULE_DEFAULT_WINDOWS):
            occ_dict = entry[occ_dict_key]
            if occ_dict.get(sched_key) != occ_id and 0 < rem <= window_secs:
                occ_dict[sched_key] = occ_id
                save_data(guild_data)
                await _send_ping(channel, role_id, get_name(entry, sched_key), window_label)


async def _send_ping(channel, role_id, label, window_label):
    try:
        msg = await channel.send(f"<@&{role_id}> **{label}** in {window_label}!",
                                  allowed_mentions=discord.AllowedMentions(roles=True))
    except Exception as e:
        print(f"[PING] {label} failed: {e}")
        return False

    async def _delete_later():
        await asyncio.sleep(3600)
        try:
            await msg.delete()
        except Exception:
            pass
    asyncio.create_task(_delete_later())
    return True


def _unbind(guild_id, entry, reason):
    print(f"[TICK] guild {guild_id}: {reason} — unbinding (run /setup again to re-enable)")
    entry["channel_id"] = None
    entry["message_id"] = None
    save_data(guild_data)


async def _resolve_channel(guild_id, entry):
    """Shared by both loops: get_channel is a local cache lookup (no API call),
    so calling this every second in ping_loop doesn't add request load — only
    the rare fetch_channel fallback and the actual ping send do."""
    if not entry.get("channel_id"):
        return None
    channel = client.get_channel(entry["channel_id"])
    if channel is not None:
        return channel
    try:
        return await client.fetch_channel(entry["channel_id"])
    except (discord.NotFound, discord.Forbidden):
        _unbind(guild_id, entry, "board channel was deleted or is no longer accessible")
    except Exception as e:
        print(f"[TICK] guild {guild_id}: channel fetch failed: {e}")
    return None


@tasks.loop(seconds=1)
async def ping_loop():
    """Separate from refresh_loop (which only edits the board every 5s) so
    alerts fire within ~1s of the 15m/5m mark instead of drifting late."""
    now_ts = datetime.now(MOSCOW).timestamp()
    for guild_id, entry in list(guild_data.items()):
        if not entry.get("ping_roles"):
            continue
        channel = await _resolve_channel(guild_id, entry)
        if channel is None:
            continue
        await _check_pings(guild_id, entry, channel, now_ts)


@ping_loop.before_loop
async def before_ping():
    await client.wait_until_ready()


@tasks.loop(seconds=5)
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

        channel = await _resolve_channel(guild_id, entry)
        if channel is None:
            continue

        embed = build_embed(entry)
        try:
            if entry.get("message_id"):
                msg = await channel.fetch_message(entry["message_id"])
                await msg.edit(embed=embed)
            else:
                msg = await channel.send(embed=embed, view=PresetView(entry))
                entry["message_id"] = msg.id
                save_data(guild_data)
        except discord.NotFound:
            # Someone deleted the board message by hand — stop chasing it instead
            # of silently respawning a new one every 5s; /setup rebinds cleanly.
            _unbind(guild_id, entry, "board message was deleted")
        except discord.Forbidden:
            _unbind(guild_id, entry, "lost permission to post in the board channel")
        except discord.RateLimited:
            # max_ratelimit_timeout makes this fire instead of blocking through a
            # long retry — just skip this tick, the next one is only 5s away, and
            # skipping fast keeps request capacity free for ping_loop's alerts.
            print(f"[TICK] guild {guild_id}: rate limited, skipping this tick")
        except Exception as e:
            print(f"[TICK] guild {guild_id} failed: {e}")
    if expired_any:
        save_data(guild_data)


@refresh_loop.before_loop
async def before_refresh():
    await client.wait_until_ready()


# ── Slash commands ───────────────────────────────────────────────────────────────
@client.tree.command(name="setup", description="Post the live ArcheAge timer board in this channel")
@require_permission("setup")
async def setup_cmd(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    # Posted first so it lands above the board (Discord orders by send time).
    await interaction.channel.send(embed=build_role_embed(entry), view=RoleButtonView(entry))
    embed = build_embed(entry)
    msg = await interaction.channel.send(embed=embed, view=PresetView(entry))
    entry["channel_id"] = interaction.channel_id
    entry["message_id"] = msg.id
    save_data(guild_data)
    await _reply_dismiss(interaction, "Timer board posted — it'll update every 5s.")


timer_group = app_commands.Group(name="timer", description="Custom countdown timers (guild boss respawns etc.)")


@timer_group.command(name="start", description="Start a custom countdown timer")
@app_commands.describe(name="Timer name (e.g. Kraken)", hours="Duration in hours (e.g. 2 or 1.5)")
@require_permission("timer")
async def timer_start(interaction: discord.Interaction, name: str, hours: float):
    if hours <= 0 or hours > 72:
        await _reply_dismiss(interaction, "Hours must be between 0 and 72.")
        return
    entry = gd(interaction.guild_id)
    name = name.strip()[:24] or "timer"
    now_ts = datetime.now(MOSCOW).timestamp()
    # Duplicate guard only (no permission change) — blocks double-submits/retries
    # from spawning two timers under the same name that would each ping on their
    # own schedule.
    existing = next((t for t in entry["custom_timers"]
                      if t["name"] == name and t["end"] > now_ts), None)
    if existing:
        display = _custom_timer_name(entry, {"name": name})
        await _reply_dismiss(interaction, f"**{display}** is already running — "
                              f"{fmt_rem(existing['end'] - now_ts)} left.")
        return
    end = now_ts + hours * 3600
    entry["custom_timers"].append({"name": name, "end": end})
    entry["custom_timers"].sort(key=lambda t: t["end"])
    save_data(guild_data)
    display_name = _custom_timer_name(entry, {"name": name})
    # Ephemeral (only you see this) so it doesn't leave a permanent message behind —
    # the timer itself shows up under Guild Timers on the live board within 5s.
    await _reply_dismiss(
        interaction,
        f"Timer started: **{display_name}** — {dur_label(hours)} ({fmt_rem(hours * 3600)} left). "
        "It'll appear on the live board within 5s.")


@timer_group.command(name="list", description="List running custom timers")
@require_permission("timer")
async def timer_list(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    if not entry["custom_timers"]:
        await _reply_dismiss(interaction, "No custom timers running.")
        return
    now_ts = datetime.now(MOSCOW).timestamp()
    lines = [f"⏱ **{_custom_timer_name(entry, t)}** — {fmt_rem(t['end'] - now_ts)} left"
             for t in entry["custom_timers"]]
    await _reply_dismiss(interaction, "\n".join(lines))


@timer_group.command(name="cancel", description="Cancel a running custom timer")
@app_commands.describe(name="Name of the timer to cancel")
@require_permission("timer")
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


roles_group = app_commands.Group(name="roles", description="Configure which role gets pinged 15m and 5m before a timer starts")


@roles_group.command(name="set", description="Ping a role 15 minutes and 5 minutes before this timer starts")
@app_commands.describe(target="Which timer/event", role="Role to ping")
@app_commands.choices(target=[app_commands.Choice(name=label, value=key) for key, label in PING_TARGETS])
@require_permission("roles")
async def roles_set(interaction: discord.Interaction, target: app_commands.Choice[str], role: discord.Role):
    entry = gd(interaction.guild_id)
    entry["ping_roles"][target.value] = role.id
    save_data(guild_data)
    await _reply_dismiss(interaction, f"**{get_name(entry, target.value)}** will now ping {role.mention} "
                          f"{_alert_timing_text(target.value)} before it starts.")


@roles_group.command(name="clear", description="Stop pinging a role for this timer")
@app_commands.describe(target="Which timer/event")
@app_commands.choices(target=[app_commands.Choice(name=label, value=key) for key, label in PING_TARGETS])
@require_permission("roles")
async def roles_clear(interaction: discord.Interaction, target: app_commands.Choice[str]):
    entry = gd(interaction.guild_id)
    had = entry["ping_roles"].pop(target.value, None) is not None
    name = get_name(entry, target.value)
    save_data(guild_data)
    await _reply_dismiss(interaction, f"Cleared the ping role for **{name}**."
                          if had else f"**{name}** had no ping role set.")


@roles_group.command(name="list", description="Show configured ping roles")
async def roles_list(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    lines = [f"**{get_name(entry, key)}** — " + (f"<@&{entry['ping_roles'][key]}>" if key in entry["ping_roles"] else "not set")
             for key, label in PING_TARGETS]
    await _reply_dismiss(interaction, "\n".join(lines))


@roles_group.command(name="message", description="Post a permanent self-assign button message for the four ping roles")
@require_permission("roles")
async def roles_message(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    await interaction.channel.send(embed=build_role_embed(entry), view=RoleButtonView(entry))
    await _reply_dismiss(interaction, "Posted.")


client.tree.add_command(roles_group)


language_group = app_commands.Group(name="language", description="Choose the board/ping language (English or Russian)")
LANGUAGE_CHOICES = [app_commands.Choice(name="English", value="en"),
                     app_commands.Choice(name="Russian", value="ru")]


@language_group.command(name="set", description="Set the board and ping language for this server")
@app_commands.describe(language="English or Russian")
@app_commands.choices(language=LANGUAGE_CHOICES)
@require_permission("language")
async def language_set(interaction: discord.Interaction, language: app_commands.Choice[str]):
    entry = gd(interaction.guild_id)
    entry["language"] = language.value
    save_data(guild_data)
    await _reply_dismiss(interaction, f"Language set to **{language.name}**. The board updates within "
                          "5s; run `/setup` again to refresh button labels on a fresh message.")


@language_group.command(name="show", description="Show the current board/ping language")
async def language_show(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    name = "Russian" if entry.get("language") == "ru" else "English"
    await _reply_dismiss(interaction, f"Current language: **{name}**.")


client.tree.add_command(language_group)


names_group = app_commands.Group(name="names", description="Set this server's own event/boss names per language")


@names_group.command(name="set", description="Set an event/boss's name for a language (e.g. a Russian alias)")
@app_commands.describe(key="Which event/boss", language="English or Russian", text="The name to display")
@app_commands.choices(language=LANGUAGE_CHOICES)
@require_permission("names")
async def names_set(interaction: discord.Interaction, key: str, language: app_commands.Choice[str], text: str):
    if key not in DEFAULT_NAMES:
        await _reply_dismiss(interaction, f"Unknown event key `{key}` — pick one from the autocomplete list.")
        return
    entry = gd(interaction.guild_id)
    entry["event_names"].setdefault(key, {})[language.value] = text.strip()[:48]
    save_data(guild_data)
    await _reply_dismiss(interaction, f"**{DEFAULT_NAMES[key]}** ({language.name}) will now show as "
                          f"**{text.strip()[:48]}**.")


@names_set.autocomplete("key")
async def names_set_autocomplete(interaction: discord.Interaction, current: str):
    current = current.lower()
    return [app_commands.Choice(name=name, value=key) for key, name in DEFAULT_NAMES.items()
            if current in key.lower() or current in name.lower()][:25]


@names_group.command(name="clear", description="Reset an event/boss's name for a language back to default")
@app_commands.describe(key="Which event/boss", language="English or Russian")
@app_commands.choices(language=LANGUAGE_CHOICES)
@require_permission("names")
async def names_clear(interaction: discord.Interaction, key: str, language: app_commands.Choice[str]):
    if key not in DEFAULT_NAMES:
        await _reply_dismiss(interaction, f"Unknown event key `{key}` — pick one from the autocomplete list.")
        return
    entry = gd(interaction.guild_id)
    had = entry["event_names"].get(key, {}).pop(language.value, None) is not None
    save_data(guild_data)
    await _reply_dismiss(interaction, f"Reset **{DEFAULT_NAMES[key]}** ({language.name}) to default."
                          if had else f"**{DEFAULT_NAMES[key]}** ({language.name}) had no override set.")


@names_clear.autocomplete("key")
async def names_clear_autocomplete(interaction: discord.Interaction, current: str):
    return await names_set_autocomplete(interaction, current)


@names_group.command(name="list", description="Show all event/boss names in both languages")
async def names_list(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    lines = []
    for key, default_en in sorted(DEFAULT_NAMES.items(), key=lambda kv: kv[1]):
        overrides = entry["event_names"].get(key, {})
        en = overrides.get("en", default_en)
        ru = overrides.get("ru", DEFAULT_NAMES_RU.get(key, default_en))
        lines.append(f"**{default_en}** — EN: {en} · RU: {ru}")
    # Discord messages cap at 2000 chars / embed descriptions at 4096; chunk defensively.
    text = "\n".join(lines)
    await _reply_dismiss(interaction, text[:3900] + ("\n…" if len(text) > 3900 else ""))


client.tree.add_command(names_group)


permissions_group = app_commands.Group(name="permissions",
                                        description="Configure which permission level each command/button needs on this server")
PERMISSION_LEVEL_CHOICES = [app_commands.Choice(name=label, value=key)
                            for key, label in PERMISSION_LEVEL_LABELS.items()]
PERMISSION_TARGET_CHOICES = [app_commands.Choice(name=label, value=key) for key, label in PERMISSION_TARGETS]


@permissions_group.command(name="set", description="Set the permission level required for a command/button")
@app_commands.describe(target="Which command/button (see /permissions list for what each one does)",
                        level="Required permission level")
@app_commands.choices(target=PERMISSION_TARGET_CHOICES, level=PERMISSION_LEVEL_CHOICES)
@app_commands.checks.has_permissions(manage_guild=True)
async def permissions_set(interaction: discord.Interaction, target: app_commands.Choice[str],
                           level: app_commands.Choice[str]):
    # Hardcoded Manage Server (not require_permission) — this command controls
    # every other permission gate, so its own gate can't be the thing it lowers.
    entry = gd(interaction.guild_id)
    entry["permissions"][target.value] = level.value
    save_data(guild_data)
    await _reply_dismiss(interaction, f"**{target.name}** now requires **{level.name}** on this server.")


@permissions_group.command(name="clear", description="Reset a command/button's permission level back to default")
@app_commands.describe(target="Which command/button")
@app_commands.choices(target=PERMISSION_TARGET_CHOICES)
@app_commands.checks.has_permissions(manage_guild=True)
async def permissions_clear(interaction: discord.Interaction, target: app_commands.Choice[str]):
    entry = gd(interaction.guild_id)
    had = entry["permissions"].pop(target.value, None) is not None
    save_data(guild_data)
    default_label = PERMISSION_LEVEL_LABELS[DEFAULT_PERMISSION_LEVELS[target.value]]
    await _reply_dismiss(interaction, f"**{target.name}** reset to the default (**{default_label}**)."
                          if had else f"**{target.name}** was already at its default.")


@permissions_group.command(name="list", description="Show the current permission level and what each command/button does")
async def permissions_list(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    lines = []
    for key, label in PERMISSION_TARGETS:
        level = _permission_level(entry, key)
        overridden = " *(overridden)*" if key in entry["permissions"] else ""
        lines.append(f"**{label}** — {PERMISSION_LEVEL_LABELS[level]}{overridden}\n"
                      f"> {PERMISSION_TARGET_DESCRIPTIONS[key]}")
    text = "\n\n".join(lines)
    await _reply_dismiss(interaction, text[:1950] + ("\n…" if len(text) > 1950 else ""))


client.tree.add_command(permissions_group)


buttons_group = app_commands.Group(name="buttons", description="Hide/show individual buttons on this server's board and role message")
BUTTON_CHOICES = [app_commands.Choice(name=label, value=cid) for cid, label in BUTTON_REGISTRY]


@buttons_group.command(name="hide", description="Hide a button on this server (repost via /setup or /roles message to apply)")
@app_commands.describe(button="Which button")
@app_commands.choices(button=BUTTON_CHOICES)
@require_permission("buttons")
async def buttons_hide(interaction: discord.Interaction, button: app_commands.Choice[str]):
    entry = gd(interaction.guild_id)
    if button.value not in entry["hidden_buttons"]:
        entry["hidden_buttons"].append(button.value)
        save_data(guild_data)
    await _reply_dismiss(interaction, f"**{button.name}** hidden on this server. Run `/setup` "
                          "(or `/roles message` for role buttons) again to repost without it.")


@buttons_group.command(name="show", description="Un-hide a button on this server")
@app_commands.describe(button="Which button")
@app_commands.choices(button=BUTTON_CHOICES)
@require_permission("buttons")
async def buttons_show(interaction: discord.Interaction, button: app_commands.Choice[str]):
    entry = gd(interaction.guild_id)
    had = button.value in entry["hidden_buttons"]
    if had:
        entry["hidden_buttons"].remove(button.value)
        save_data(guild_data)
    await _reply_dismiss(interaction, (f"**{button.name}** will show again — run `/setup` "
                          "(or `/roles message`) again to repost with it.") if had
                          else f"**{button.name}** wasn't hidden.")


@buttons_group.command(name="list", description="Show which buttons are hidden on this server")
async def buttons_list(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    lines = [f"**{label}** — {'hidden' if cid in entry['hidden_buttons'] else 'shown'}"
             for cid, label in BUTTON_REGISTRY]
    await _reply_dismiss(interaction, "\n".join(lines))


client.tree.add_command(buttons_group)


@client.tree.command(name="events", description="One-off snapshot of live/upcoming events")
async def events_cmd(interaction: discord.Interaction):
    entry = gd(interaction.guild_id)
    embed = build_embed(entry)
    await _reply_dismiss(interaction, embed=embed)


@client.tree.command(name="clear", description="Delete this bot's own messages in this channel")
@require_permission("clear_cmd")
async def clear_cmd(interaction: discord.Interaction):
    # Only ever touches messages this bot itself sent (board/ping/confirmation
    # leftovers) — never other users' messages, so it's safe without a confirm
    # step. Gated on Manage Messages, same bar as the preset timer buttons.
    await interaction.response.defer(ephemeral=True)
    bot_id = client.user.id
    try:
        deleted = await interaction.channel.purge(limit=1000, check=lambda m: m.author.id == bot_id)
    except discord.Forbidden:
        await interaction.followup.send(
            "I don't have permission to delete messages here — check I have "
            "**Manage Messages** and **Read Message History** in this channel.",
            ephemeral=True)
        return
    except Exception as e:
        print(f"[CLEAR] guild {interaction.guild_id} failed: {e}")
        await interaction.followup.send(f"Clear failed: {e}", ephemeral=True)
        return

    entry = guild_data.get(str(interaction.guild_id))
    if entry and entry.get("channel_id") == interaction.channel_id:
        _unbind(interaction.guild_id, entry, "board message cleared via /clear")
    await interaction.followup.send(
        f"Deleted {len(deleted)} of my messages. Run `/setup` again to repost the board.",
        ephemeral=True)


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
