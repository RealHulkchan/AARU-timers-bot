# AARU Timers — Admin Guide

## Setup
1. Invite the bot with: View Channel, Send Messages, Embed Links, Read Message
   History, Manage Messages, Manage Roles.
2. Server Settings → Roles: drag the bot's role **above** any role it should
   assign (JMG/Rangora/Morpheus/Guild Boss/Skyfin/Halcy).
3. Run `/setup` in the channel you want the board in.

Everything except `/setup`, `/timer`, and `/clear` lives under one top-level
`/config` command, and each configuration area is exactly **one** command —
`/config roles`, `/config pings`, and `/config board` add a `section`
dropdown on top of the `action` dropdown (Set/Clear/List/Hide/Show/etc.), so
one command covers everything that area does (e.g. `/config board` covers
Wording, Category, and Events all in one entry in the "/" picker).

## Commands
| Command | Permission | Does |
|---|---|---|
| `/setup` | Manage Server | Post/move the board + opt-in role message here |
| `/clear` | Manage Server | Delete the bot's own messages in this channel |
| `/timer start/list/cancel` | Manage Messages | Manual countdown timers (start/cancel autocomplete the 3 presets, localized) |
| `/config roles` (section: Ping/Message/Visibility, action: Set/Clear/List/Hide/Show) | Manage Server | Bind ping roles, repost the self-assign message, or hide/show it entirely |
| `/config language` (action: Set/Show) | Manage Server | Toggle board/pings between English/Russian |
| `/config names` (action: Set/Clear/List) | Manage Server | Rename any event/boss per language |
| `/config permissions` (action: Set/Clear/List) | Manage Server (hardcoded) | Set the required level for any of the above, per server |
| `/config buttons` (action: Hide/Show/List) | Manage Server | Hide/show individual preset/role buttons |
| `/config pings` (section: Message/Alerts, action: Set/Reset/Disable/Enable/List) | Manage Server | Custom ping wording; silence a target's alerts without unbinding its role |
| `/config board` (section: Wording/Category/Events, action: Set/Reset/List/Hide/Show) | Manage Server | Customize board wording, move events between Bosses & PVP / Upcoming Events, or hide events entirely |
| `/config emoji` (action: Set/Reset/List) | Manage Server | Customize the icon next to any board header, boss, or event — every UI header, every scheduled event, and the Guild Boss/Morpheus/Rangora preset timers, all independently, including this server's own custom emoji |

Preset buttons (`+ Guild Boss/Morph/Rangora`) require Send Messages, and
`/timer start/list/cancel` requires Manage Messages — both just start/manage
a countdown, so they're kept lower-friction than the rest for regular raid
members. Role self-assign buttons are open to everyone by design (they
bypass the permission system entirely). Every other command/button changes
bot state visible to the whole server (bindings, wording, layout, board
presence, deleting messages) and defaults to Manage Server. All of these are
per-server overridable via `/config permissions` — changing a default here
never touches a server that's already set its own level for that target.

After `/config language` (action: Set) or a button/label change, run `/setup`
(or `/config roles` section:Message) again to repost a fresh message with the
update.

## Troubleshooting
- **Board won't post / "Missing Access"**: check channel-specific permission
  overwrites, not just the bot's server-wide role.
- **Command missing from picker**: Discord's own client-side command cache
  can take up to ~1hr to refresh even after a full restart — this is
  separate from the bot's own registration (check the Railway startup logs
  for a `[SYNC] N global commands: [...]` line to confirm the bot's side
  synced correctly).
- **Role buttons don't work**: bot needs Manage Roles + must be above that role.
- **Board stuck**: it self-unbinds if the message/channel is gone — `/setup` again.
- **`/clear` hangs**: bot itself needs Manage Messages + Read Message History
  in that channel.
