# AARU Timers — Admin Reference

Everything except `/setup`, `/timer`, and `/clear` nests under one
top-level `/config` command (e.g. `/config roles ping`). Within `/config`,
most subcommands bundle several old separate commands into one `action`
dropdown parameter (Set/Clear/List/Hide/Show/etc.) instead of registering
a separate command per verb, to keep the "/" picker short.

## Commands

| Command | Does |
|---|---|
| `/setup` | Post/move the live board + role message into this channel |
| `/timer start / list / cancel` | Manual countdown timers (start/cancel autocomplete the 3 presets, localized) |
| `/config roles ping` (action: Set/Clear/List) | Bind/unbind/list which role gets pinged before a timer/event |
| `/config roles message` | Repost the self-assign buttons |
| `/config roles visibility` (action: Hide/Show) | Remove/repost the whole opt-in role message |
| `/config language` (action: Set/Show) | Toggle English/Russian |
| `/config names` (action: Set/Clear/List) | Custom per-server event/boss names, per language |
| `/config permissions` (action: Set/Clear/List) | Per-server permission level for each gated feature |
| `/config buttons` (action: Hide/Show/List) | Hide/show individual buttons |
| `/config pings message` (action: Set/Reset) | Custom ping wording |
| `/config pings alerts` (action: Disable/Enable/List) | Silence a target's alerts without unbinding its role |
| `/config board wording` (action: Set/Reset/List) | Customize the board's "6m left"/"in 1h" wording |
| `/config board category` (action: Set/Reset/List) | Move an event between Bosses & PVP and Upcoming Events, per server |
| `/config board events` (action: Hide/Show/List) | Remove an event from the board (and its pings) entirely |
| `/clear` | Delete the bot's own messages in this channel |

## Ping targets

Guild Boss, JMG, Morpheus, Rangora, Skyfin, Halcy (= Golden Plains Battle), Tokens (= Prairie or Invasion) — 15m+5m alerts, Tokens is 30m+5m. Each bindable to a role via `/config roles ping` (action: Set), self-assignable by members via button.

## Permission targets (`/config permissions` action:Set target:\<x\>)

preset_timers, timer, setup, roles, language, names, clear_cmd, buttons, pings, board — each independently set to Everyone / Send Messages / Manage Messages / Manage Server.

Defaults: preset buttons = Everyone. `setup`, `language`, `board` (covers `/config roles visibility` too) = Manage Server — these change how the bot presents to the *whole server* (layout, language, wording, event visibility, or the opt-in message's presence). Everything else = Manage Messages. `/config permissions` itself is hardcoded Manage Server.

## Notes

- Board refreshes every 5s; ping checks run on a separate 1s loop.
- Renaming via `/config names` (action: Set) never breaks matching — internal keys are fixed, only display text changes.
- `/clear` only deletes this bot's own messages, never others'.
- Button/label/wording changes need a repost (`/setup` or `/config roles message`) to show on a new message.
- Russian pings and board wording ("6m left" / "in 1h") are built-in defaults when `/config language` (action: Set) is Russian — override either per server with `/config pings message` / `/config board wording`.
- Hiding an event (`/config board events` action:Hide) removes it from the board AND stops it pinging, unlike `/config pings alerts` (action: Disable, silences pings only) or `/config board category` (action: Set, moves it, still visible).
