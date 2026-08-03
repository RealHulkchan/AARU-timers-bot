# AARU Timers — Admin Reference

## Commands

| Command | Does |
|---|---|
| `/setup` | Post/move the live board + role message into this channel |
| `/timer start / list / cancel` | Manual countdown timers |
| `/roles set / clear / list / message` | Bind/unbind ping roles; repost self-assign buttons |
| `/language set / show` | Toggle English/Russian |
| `/names set / clear / list` | Custom per-server event/boss names, per language |
| `/permissions set / clear / list` | Per-server permission level for each gated feature |
| `/buttons hide / show / list` | Hide/show individual buttons |
| `/pings message / message-reset / disable / enable / list` | Custom ping wording; silence a target without unbinding its role |
| `/events` | Private board snapshot |
| `/clear` | Delete the bot's own messages here |

## Ping targets

Guild Boss, JMG, Morpheus, Rangora, Skyfin, Halcy (= Golden Plains Battle), Tokens (= Prairie or Invasion) — 15m+5m alerts, Tokens is 30m+5m. Each bindable to a role via `/roles set`, self-assignable by members via button.

## Permission targets (`/permissions set target:<x>`)

preset_timers, timer, setup, roles, language, names, clear_cmd, buttons, pings — each independently set to Everyone / Send Messages / Manage Messages / Manage Server. Defaults: preset buttons = Everyone, everything else = Manage Messages. `/permissions` itself is hardcoded Manage Server.

## Notes

- Board refreshes every 5s; ping checks run on a separate 1s loop.
- Renaming via `/names set` never breaks matching — internal keys are fixed, only display text changes.
- `/clear` only deletes this bot's own messages, never others'.
- Button/label changes need a repost (`/setup` or `/roles message`) to show on a new message.
