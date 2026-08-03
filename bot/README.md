# AARU Timers — Admin Guide

## Setup
1. Invite the bot with: View Channel, Send Messages, Embed Links, Read Message
   History, Manage Messages, Manage Roles.
2. Server Settings → Roles: drag the bot's role **above** any role it should
   assign (JMG/Rangora/Morpheus/Guild Boss/Skyfin/Halcy).
3. Run `/setup` in the channel you want the board in.

Everything except `/setup`, `/timer`, and `/clear` lives under one top-level
`/config` command (e.g. `/config roles ping`) to keep the "/" picker short.
Within `/config`, most subcommands also bundle what used to be several
separate commands into one `action` dropdown parameter (Set/Clear/List/
Hide/Show/etc.), so the picker stays short even once filtered.

## Commands
| Command | Permission | Does |
|---|---|---|
| `/setup` | Manage Server | Post/move the board + opt-in role message here |
| `/clear` | Manage Messages | Delete the bot's own messages in this channel |
| `/timer start/list/cancel` | — (configure via Integrations tab if wanted) | Manual countdown timers (start/cancel autocomplete the 3 presets, localized) |
| `/config roles ping` (action: Set/Clear/List) | Manage Messages | Bind a role to ping before Guild Boss/JMG/Morpheus/Rangora/Skyfin/Halcy/Tokens |
| `/config roles message` | Manage Messages | Re-post just the self-assign role buttons |
| `/config roles visibility` (action: Hide/Show) | Manage Server | Remove/repost the whole opt-in role message |
| `/config language` (action: Set/Show) | Manage Server (Set only) | Toggle board/pings between English/Russian |
| `/config names` (action: Set/Clear/List) | Manage Messages | Rename any event/boss per language |
| `/config permissions` (action: Set/Clear/List) | Manage Server (hardcoded) | Set the required level for any of the above, per server |
| `/config buttons` (action: Hide/Show/List) | Manage Messages | Hide/show individual preset/role buttons |
| `/config pings message` (action: Set/Reset) | Manage Messages | Custom ping wording |
| `/config pings alerts` (action: Disable/Enable/List) | Manage Messages | Silence a target's alerts without unbinding its role |
| `/config board wording` (action: Set/Reset/List) | Manage Server | Customize the board's own "6m left"/"in 1h" wording |
| `/config board category` (action: Set/Reset/List) | Manage Server | Move an event between Bosses & PVP and Upcoming Events, per server |
| `/config board events` (action: Hide/Show/List) | Manage Server | Remove an event from the board (and its pings) entirely |

Preset buttons (`+ Guild Boss/Morph/Rangora`) require Manage Messages to click.
Role self-assign buttons are open to everyone by design.
Anything that changes the bot's presentation for the whole server (`/setup`,
`/config language`, `/config board`, `/config roles visibility`) defaults
to Manage Server; narrower per-binding/per-timer actions default to Manage
Messages. All are per-server overridable via `/config permissions`.

After `/config language` (action: Set) or a button/label change, run `/setup`
(or `/config roles message`) again to repost a fresh message with the update.

## Troubleshooting
- **Board won't post / "Missing Access"**: check channel-specific permission
  overwrites, not just the bot's server-wide role.
- **Command missing from picker**: can take ~1hr to propagate; also fully
  restart Discord.
- **Role buttons don't work**: bot needs Manage Roles + must be above that role.
- **Board stuck**: it self-unbinds if the message/channel is gone — `/setup` again.
- **`/clear` hangs**: bot itself needs Manage Messages + Read Message History
  in that channel.
