# AARU Timers — Admin Reference

Everything except `/setup`, `/timer`, and `/clear` nests under one
top-level `/config` command. Each configuration area is exactly **one**
command — `/config roles`, `/config pings`, and `/config board` add a
`section` dropdown on top of the `action` dropdown (Set/Clear/List/Hide/
Show/etc.), so a single command covers everything that area does instead of
registering a separate command per verb, keeping the "/" picker short.

## Commands

| Command | Does |
|---|---|
| `/setup` | Post/move the live board + role message into this channel |
| `/timer start / list / cancel` | Manual countdown timers (start/cancel autocomplete the 3 presets, localized) |
| `/config roles` (section: Ping/Message/Visibility) | Bind/unbind/list ping roles; repost the self-assign buttons; hide/show the whole opt-in message |
| `/config language` (action: Set/Show) | Toggle English/Russian |
| `/config names` (action: Set/Clear/List) | Custom per-server event/boss names, per language |
| `/config permissions` (action: Set/Clear/List) | Per-server permission level for each gated feature |
| `/config buttons` (action: Hide/Show/List) | Hide/show individual buttons |
| `/config pings` (section: Message/Alerts) | Custom ping wording; silence/restore a target's alerts without unbinding its role |
| `/config board` (section: Wording/Category/Events) | Customize row wording, move events between Bosses & PVP / Upcoming Events, or hide events entirely |
| `/config emoji` (action: Set/Reset/List, type to search `key`) | Customize the icon next to any board header, boss, or event — every UI header, every scheduled event, and Guild Boss/Morpheus/Rangora, all independently, including this server's own custom emoji |
| `/clear` | Delete the bot's own messages in this channel |

## Ping targets

Guild Boss, JMG, Morpheus, Rangora, Skyfin, Halcy (= Golden Plains Battle), Tokens (= Prairie or Invasion) — 15m+5m alerts, Tokens is 30m+5m. Each bindable to a role via `/config roles` (section: Ping, action: Set), self-assignable by members via button.

## Permission targets (`/config permissions` action:Set target:\<x\>)

preset_timers, timer, setup, roles, language, names, clear_cmd, buttons, pings, board — each independently set to Everyone / Send Messages / Manage Messages / Manage Server.

Defaults: preset buttons = Send Messages, `timer` = Manage Messages — both just start/manage a countdown, so they're kept lower-friction than the rest. Everything else = Manage Server, since it all changes bot state visible to the whole server (bindings, wording, layout, board presence, deleting messages). `/config permissions` itself is hardcoded Manage Server. These are fallback defaults only — a guild that's already set its own level for a target via `/config permissions` keeps that override.

## Notes

- Board refreshes every 5s; ping checks run on a separate 1s loop.
- Renaming via `/config names` (action: Set) never breaks matching — internal keys are fixed, only display text changes.
- `/clear` only deletes this bot's own messages, never others'.
- Button/label/wording changes need a repost (`/setup` or `/config roles` section:Message) to show on a new message.
- Russian pings and board wording ("6m left" / "in 1h") are built-in defaults when `/config language` (action: Set) is Russian — override either per server with `/config pings` (section: Message) / `/config board` (section: Wording).
- Hiding an event (`/config board` section:Events action:Hide) removes it from the board AND stops it pinging, unlike `/config pings` (section: Alerts, action: Disable, silences pings only) or `/config board` (section: Category, action: Set, moves it, still visible).
