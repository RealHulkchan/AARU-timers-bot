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
| `/clear` | Manage Messages | Delete the bot's own messages in this channel |
| `/timer start/list/cancel` | — (configure via Integrations tab if wanted) | Manual countdown timers (start/cancel autocomplete the 3 presets, localized) |
| `/config roles` (section: Ping/Message/Visibility, action: Set/Clear/List/Hide/Show) | Ping/Message: Manage Messages; Visibility: Manage Server | Bind ping roles, repost the self-assign message, or hide/show it entirely |
| `/config language` (action: Set/Show) | Manage Server (Set only) | Toggle board/pings between English/Russian |
| `/config names` (action: Set/Clear/List) | Manage Messages | Rename any event/boss per language |
| `/config permissions` (action: Set/Clear/List) | Manage Server (hardcoded) | Set the required level for any of the above, per server |
| `/config buttons` (action: Hide/Show/List) | Manage Messages | Hide/show individual preset/role buttons |
| `/config pings` (section: Message/Alerts, action: Set/Reset/Disable/Enable/List) | Manage Messages | Custom ping wording; silence a target's alerts without unbinding its role |
| `/config board` (section: Wording/Category/Events, action: Set/Reset/List/Hide/Show) | Manage Server | Customize board wording, move events between Bosses & PVP / Upcoming Events, or hide events entirely |

Preset buttons (`+ Guild Boss/Morph/Rangora`) require Manage Messages to click.
Role self-assign buttons are open to everyone by design.
Anything that changes the bot's presentation for the whole server (`/setup`,
`/config language`, `/config board`, `/config roles` section:Visibility)
defaults to Manage Server; narrower per-binding/per-timer actions default to
Manage Messages. All are per-server overridable via `/config permissions`.

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
