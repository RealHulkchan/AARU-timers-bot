# AARU Timers — Admin Guide

## Setup
1. Invite the bot with: View Channel, Send Messages, Embed Links, Read Message
   History, Manage Messages, Manage Roles.
2. Server Settings → Roles: drag the bot's role **above** any role it should
   assign (JMG/Rangora/Morpheus/Guild Boss/Skyfin/Halcy).
3. Run `/setup` in the channel you want the board in.

## Commands
| Command | Permission | Does |
|---|---|---|
| `/setup` | Manage Server | Post/move the board + opt-in role message here |
| `/clear` | Manage Messages | Delete the bot's own messages in this channel |
| `/events` | — | Private snapshot of the board |
| `/timer start/list/cancel` | — (configure via Integrations tab if wanted) | Manual countdown timers |
| `/roles set/clear/list` | Manage Messages | Bind a role to ping before Guild Boss/JMG/Morpheus/Rangora/Skyfin/Halcy/Tokens |
| `/roles message` | Manage Messages | Re-post just the self-assign role buttons |
| `/roles hide/show` | Manage Server | Remove/repost the whole opt-in role message |
| `/language set/show` | Manage Server (set only) | Toggle board/pings between English/Russian |
| `/names set/clear/list` | Manage Messages (set/clear only) | Rename any event/boss per language |
| `/permissions set/clear/list` | Manage Server (hardcoded) | Set the required level for any of the above, per server |
| `/buttons hide/show/list` | Manage Messages | Hide/show individual preset/role buttons |
| `/pings message/message-reset/disable/enable/list` | Manage Messages | Custom ping wording; silence a target without unbinding its role |
| `/board time-format/time-reset/time-list` | Manage Server | Customize the board's own "6m left"/"in 1h" wording |

Preset buttons (`+ Guild Boss/Morph/Rangora`) require Manage Messages to click.
Role self-assign buttons are open to everyone by design.
Anything that changes the bot's presentation for the whole server (`/setup`,
`/language set`, `/board`, `/roles hide|show`) defaults to Manage Server;
narrower per-binding/per-timer actions default to Manage Messages. All are
per-server overridable via `/permissions`.

After `/language set` or a button/label change, run `/setup` (or `/roles
message`) again to repost a fresh message with the update.

## Troubleshooting
- **Board won't post / "Missing Access"**: check channel-specific permission
  overwrites, not just the bot's server-wide role.
- **Command missing from picker**: can take ~1hr to propagate; also fully
  restart Discord.
- **Role buttons don't work**: bot needs Manage Roles + must be above that role.
- **Board stuck**: it self-unbinds if the message/channel is gone — `/setup` again.
- **`/clear` hangs**: bot itself needs Manage Messages + Read Message History
  in that channel.
