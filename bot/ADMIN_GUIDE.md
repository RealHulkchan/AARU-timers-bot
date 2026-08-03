# AARU Timers — Admin Reference

Everything except `/setup`, `/timer`, `/events`, and `/clear` nests under one
top-level `/config` command (e.g. `/roles set` below is `/config roles set`).

## Commands

| Command | Does |
|---|---|
| `/setup` | Post/move the live board + role message into this channel |
| `/timer start / list / cancel` | Manual countdown timers |
| `/config roles set / clear / list / message` | Bind/unbind ping roles; repost self-assign buttons |
| `/config roles hide / show` | Remove/repost the whole opt-in role message |
| `/config language set / show` | Toggle English/Russian |
| `/config names set / clear / list` | Custom per-server event/boss names, per language |
| `/config permissions set / clear / list` | Per-server permission level for each gated feature |
| `/config buttons hide / show / list` | Hide/show individual buttons |
| `/config pings message / message-reset / disable / enable / list` | Custom ping wording; silence a target without unbinding its role |
| `/config board time-format / time-reset / time-list` | Customize the board's "6m left"/"in 1h" wording |
| `/config board category-set / category-reset / category-list` | Move an event between Bosses & PVP and Upcoming Events, per server |
| `/config board hide-event / show-event / hidden-list` | Remove an event from the board (and its pings) entirely |
| `/events` | Private board snapshot |
| `/clear` | Delete the bot's own messages here |

## Ping targets

Guild Boss, JMG, Morpheus, Rangora, Skyfin, Halcy (= Golden Plains Battle), Tokens (= Prairie or Invasion) — 15m+5m alerts, Tokens is 30m+5m. Each bindable to a role via `/config roles set`, self-assignable by members via button.

## Permission targets (`/config permissions set target:<x>`)

preset_timers, timer, setup, roles, language, names, clear_cmd, buttons, pings, board — each independently set to Everyone / Send Messages / Manage Messages / Manage Server.

Defaults: preset buttons = Everyone. `setup`, `language`, `board` (covers `/config roles hide|show` too) = Manage Server — these change how the bot presents to the *whole server* (layout, language, wording, event visibility, or the opt-in message's presence). Everything else = Manage Messages. `/config permissions` itself is hardcoded Manage Server.

## Notes

- Board refreshes every 5s; ping checks run on a separate 1s loop.
- Renaming via `/config names set` never breaks matching — internal keys are fixed, only display text changes.
- `/clear` only deletes this bot's own messages, never others'.
- Button/label/wording changes need a repost (`/setup` or `/config roles message`) to show on a new message.
- Russian pings and board wording ("осталось {time}" / "через {time}") are built-in defaults when `/config language set` is Russian — override either per server with `/config pings message` / `/config board time-format`.
- Hiding an event (`/config board hide-event`) removes it from the board AND stops it pinging, unlike `/config pings disable` (silences pings only) or `/config board category-set` (moves it, still visible).
