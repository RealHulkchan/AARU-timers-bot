# AARU Timers — Admin Guide

A Discord bot that posts a self-updating board of ArcheAge event/boss timers and
pings roles before they start. This doc covers running the bot day-to-day as a
server admin — see the top of [discord_bot.py](discord_bot.py) for the developer/
deploy notes.

## First-time setup

1. **Invite the bot** with these permissions in the channel(s) it'll post in:
   View Channel, Send Messages, Embed Links, Read Message History, Manage
   Messages (for `/clear` and pinning), and **Manage Roles** if you want the
   self-assign ping buttons to work.
2. In Server Settings → Roles, drag the bot's own role **above** any role you
   plan to have it assign (JMG/Rangora/Morpheus/Guild Boss/Skyfin/Halcy). Discord
   blocks a bot from touching a role positioned above its own, even with Manage
   Roles granted.
3. In the channel you want the board in, run:
   ```
   /setup
   ```
   This posts two messages: the self-assign role-button embed (pinned above) and
   the live timer board (updates every 2 seconds). Both stay bound to that
   channel until you `/setup` again elsewhere.

## Day-to-day commands

### The board itself
- `/setup` — (Manage Server) post/move the board + opt-in message to the current
  channel. Re-running it does **not** delete the old messages — delete those by
  hand first if you're relocating the board, or use `/clear` (below).
- `/events` — one-off snapshot of the board, visible only to you, auto-dismisses
  after 2 minutes. Handy for checking timers without touching the pinned board.
- `/clear` — (Manage Messages) deletes this bot's own messages in the current
  channel (board, alerts, leftover confirmations). Never touches other users'
  messages. If it clears the bound board channel, the binding is dropped — run
  `/setup` again to repost.

### Custom timers (Guild Boss / Morpheus / Rangora / anything else)
- The `+ Guild Boss` / `+ Morph` / `+ Rangora` buttons under the board start a
  preset-duration timer with one click (2h / 12h / 12h respectively).
- `/timer start name:<text> hours:<number>` — start any custom timer, any name,
  any duration (0–72h). If the name matches Guild Boss/Morpheus/Rangora exactly
  it's treated as that preset for ping/translation purposes; otherwise it's just
  a plain countdown.
- `/timer list` — see what's currently running (ephemeral).
- `/timer cancel name:<text>` — cancel one (autocompletes from running timers).
- Starting a timer under a name that's already running is blocked (both via the
  buttons and `/timer start`) so double-clicks/retries can't spawn duplicates
  that would each ping independently.

**Permissions here are split on purpose:** the `+ Guild Boss/Morph/Rangora`
buttons require **Manage Messages** (hardcoded). `/timer start`/`list`/`cancel`
carry no hardcoded permission — restrict who can use those via **Server
Settings → Integrations → (this bot) → `/timer`**, Discord's native per-command
permission panel, if you want them locked down too.

### Ping roles (alerts before a timer starts)
Six targets can each have one Discord role bound to them: **Guild Boss, JMG,
Morpheus, Rangora, Skyfin, Halcy**. Bound roles get pinged twice — 15 minutes and
5 minutes before the timer/event starts, in the board's channel, and that ping
message auto-deletes after 1 hour.

- `/roles set target:<pick> role:<pick>` — (Manage Server) bind a role.
- `/roles clear target:<pick>` — (Manage Server) unbind it.
- `/roles list` — see current bindings.
- `/roles message` — post (or re-post) just the self-assign button embed without
  touching the board.

Members opt themselves in/out by clicking the matching button under the opt-in
embed — no admin action needed per member. If a target has no role bound yet,
clicking its button tells the member so instead of silently doing nothing.

### Language (English / Russian)
- `/language set language:<English|Russian>` — (Manage Server) switch the
  board, opt-in embed, button labels, and ping messages for this server.
- `/language show` — see the current setting.

Changing language takes effect on the board within 2 seconds. Button labels are
baked into a message when it's sent, so **run `/setup` again** (or `/roles
message` for just the role buttons) after switching to get labels in the new
language on a fresh message.

The 15 weekly bosses/sieges and fixed daily events (Kraken, Charybdis, Golden
Plains Battle, Skyfin, Kadum, etc.) already have built-in Russian names. The
in-game-clock dailies (JMG, Normal CR, SGCR, Hiram Rift, GR) and the four
ping-only targets (Guild Boss, Morpheus, Rangora, Halcy) don't — they show
English until set per server (see below).

### Custom event/boss names (`/names`)
Every event, boss, and ping target can have its own name per language, per
server — this is how "Golden Plains Battle" became "Halcy" here, and it's how
you'd fill in the Russian names not covered by the built-in defaults above.

- `/names set key:<autocomplete> language:<English|Russian> text:<name>` —
  (Manage Server) set a name. The `key` field autocompletes by typing part of
  the event's default English name.
- `/names clear key:<autocomplete> language:<pick>` — (Manage Server) reset one
  back to default.
- `/names list` — see every event's current EN/RU name at a glance.

Renaming something here is always safe — matching for pings, board grouping,
and timer identity is done internally by a fixed key, never by whatever name is
currently displayed, so relabeling can't break anything else.

## Troubleshooting

- **Board says "Missing Access" or won't post**: the bot lacks View Channel or
  Send Messages in that specific channel — check for a channel-level permission
  overwrite even if the bot's role has server-wide access.
- **A slash command doesn't show up in the picker**: Discord can take up to ~1
  hour to propagate a newly-added/changed global command. Also try fully
  closing and reopening Discord (not just switching channels) — the client
  caches the command list per session.
- **Role buttons don't assign the role**: check the bot has Manage Roles and is
  positioned above that role in Server Settings → Roles (see setup step 2).
- **Board stopped updating / stuck on an old message**: if someone deleted the
  board message or the bot lost access to the channel, it unbinds itself
  automatically (no more silent respawning or endless retries) — run `/setup`
  again to rebind.
- **`/clear` seems to hang**: it needs the *bot itself* to have Manage Messages
  and Read Message History in that channel — the command's own permission gate
  only checks the person running it.
