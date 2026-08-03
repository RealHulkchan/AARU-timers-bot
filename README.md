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
| `/setup` | Manage Messages | Post/move the board + opt-in role message here |
| `/clear` | Manage Messages | Delete the bot's own messages in this channel |
| `/events` | — | Private snapshot of the board |
| `/timer start/list/cancel` | — (configure via Integrations tab if wanted) | Manual countdown timers |
| `/roles set/clear/list` | Manage Messages | Bind a role to ping 15m/5m before Guild Boss/JMG/Morpheus/Rangora/Skyfin/Halcy |
| `/roles message` | Manage Messages | Re-post just the self-assign role buttons |
| `/language set/show` | Manage Messages (set only) | Toggle board/pings between English/Russian |
| `/names set/clear/list` | Manage Messages (set/clear only) | Rename any event/boss per language |

Preset buttons (`+ Guild Boss/Morph/Rangora`) require Manage Messages to click.
Role self-assign buttons are open to everyone by design.

After `/language set`, run `/setup` again to refresh button labels.

## Troubleshooting
- **Board won't post / "Missing Access"**: check channel-specific permission
  overwrites, not just the bot's server-wide role.
- **Command missing from picker**: can take ~1hr to propagate; also fully
  restart Discord.
- **Role buttons don't work**: bot needs Manage Roles + must be above that role.
- **Board stuck**: it self-unbinds if the message/channel is gone — `/setup` again.
- **`/clear` hangs**: bot itself needs Manage Messages + Read Message History
  in that channel.
