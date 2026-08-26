import asyncio
import discord
from core.actions import RadioAction, RadioState
from ui.views.player import HelpView
from ui.views.queue import FullQueueView
from ui.utils import get_feedback
from ui.i18n import t
from utils.logger import log

async def handle_prefix_commands(message: discord.Message, radio):
    """Processes traditional prefix commands in the dedicated radio channel."""
    if message.author.bot or not message.content:
        return

    config = radio.config
    if message.channel.id != config.radio_text_channel_id:
        return

    prefix = config.command_prefix
    if not message.content.startswith(prefix):
        return

    content = message.content[len(prefix):].strip()
    if not content:
        return

    parts = content.split()
    command = parts[0].lower()
    args = parts[1:]

    async def delayed_delete(msg):
        await asyncio.sleep(config.command_delete_delay)
        try:
            await msg.delete()
        except discord.Forbidden:
            log.warning(f"Could not delete message from {msg.author}: Missing 'Manage Messages' permission.")
        except Exception:
            pass

    try:
        asyncio.create_task(delayed_delete(message))

        if command in ["play", "p"]:
            if not message.author.voice:
                await message.channel.send(f"{message.author.mention} " + get_feedback("no_permission"), delete_after=config.notification_timeout)
            else:
                query = " ".join(args).strip() if args else None
                if not query:
                    if radio.status == RadioState.PAUSED:
                        radio.dispatch(RadioAction.REPLAY, user=message.author)
                    else:
                        await message.channel.send(f"{message.author.mention} " + get_feedback("nothing_playing"), delete_after=config.notification_timeout)
                else:
                    if radio.voice_channel_id is None:
                        radio.dispatch(RadioAction.JOIN, message.author.voice.channel.id, user=message.author)
                    radio.dispatch(RadioAction.ADD_EXT_LINK, query, user=message.author)
                    await message.channel.send(f"{message.author.mention} " + get_feedback("weblink_added"), delete_after=config.notification_timeout)

        elif command == "stop":
            radio.dispatch(RadioAction.STOP, user=message.author)
            await message.channel.send(f"{message.author.mention} " + get_feedback("stopping"), delete_after=config.notification_timeout)

        elif command in ["disconnect", "leave", "d", "l"]:
            radio.dispatch(RadioAction.DISCONNECT, user=message.author)
            await message.channel.send(f"{message.author.mention} " + get_feedback("severing"), delete_after=config.notification_timeout)

        elif command in ["skip", "s"]:
            if radio.queue or radio.future_queue or radio.is_navigating:
                radio.dispatch(RadioAction.SKIP, user=message.author)
                await message.channel.send(f"{message.author.mention} " + get_feedback("forwarding"), delete_after=config.notification_timeout)
            else:
                await message.channel.send(f"{message.author.mention} " + get_feedback("no_next_track"), delete_after=config.notification_timeout)

        elif command in ["back", "b"]:
            if radio.history:
                radio.dispatch(RadioAction.BACK, user=message.author)
                await message.channel.send(f"{message.author.mention} " + get_feedback("backing"), delete_after=config.notification_timeout)
            else:
                await message.channel.send(f"{message.author.mention} " + get_feedback("no_prev_track"), delete_after=config.notification_timeout)

        elif command in ["join", "j"]:
            if message.author.voice:
                radio.dispatch(RadioAction.JOIN, message.author.voice.channel.id, user=message.author)
                feedback = f"{get_feedback('syncing')} ({message.author.voice.channel.name})"
                await message.channel.send(f"{message.author.mention} " + feedback, delete_after=config.notification_timeout)
            else:
                await message.channel.send(f"{message.author.mention} " + get_feedback("no_permission"), delete_after=config.notification_timeout)

        elif command in ["volume", "v"] and args:
            try:
                vol = int(args[0])
                if 0 <= vol <= 100:
                    radio.dispatch(RadioAction.SET_VOLUME, vol / 100, user=message.author)
                    await message.channel.send(f"{message.author.mention} " + get_feedback("vol_set") + f" {vol}%", delete_after=config.notification_timeout)
                else:
                    await message.channel.send(f"{message.author.mention} " + get_feedback("vol_range_error"), delete_after=config.notification_timeout)
            except Exception:
                await message.channel.send(f"{message.author.mention} " + get_feedback("invalid_number"), delete_after=config.notification_timeout)

        elif command in ["loop", "lt"]:
            radio.dispatch(RadioAction.LOOP, user=message.author)
            msg_key = "loop_enabled" if not radio.loop_mode else "loop_disabled"
            await message.channel.send(f"{message.author.mention} {get_feedback(msg_key)}", delete_after=config.notification_timeout)

        elif command in ["loopq", "lq"]:
            radio.dispatch(RadioAction.LOOP_QUEUE, user=message.author)
            msg_key = "loop_queue_enabled" if not radio.loop_queue_mode else "loop_queue_disabled"
            await message.channel.send(f"{message.author.mention} {get_feedback(msg_key)}", delete_after=config.notification_timeout)

        elif command in ["shuffle", "sh"]:
            radio.dispatch(RadioAction.SHUFFLE, user=message.author)
            await message.channel.send(f"{message.author.mention} {get_feedback('queue_shuffled')}", delete_after=config.notification_timeout)

        elif command in ["queue", "q"]:
            view = FullQueueView(radio, page=0, user=message.author)
            await message.channel.send(view=view, delete_after=config.view_timeout)

        elif command in ["help", "h"]:
            view = HelpView(radio)
            await message.channel.send(embed=view.get_embed(), delete_after=config.view_timeout)

        elif command == "restart":
            if radio.is_admin(message.author):
                feedback = f"{get_feedback('restarting')}"
                await message.channel.send(f"{message.author.mention} {feedback}")
                radio.dispatch(RadioAction.RESTART, user=message.author)
            else:
                await message.channel.send(f"{message.author.mention} " + get_feedback("admin_only"), delete_after=5)

        elif command == "clearcache":
            if radio.is_admin(message.author):
                count = radio.clear_cache()
                await message.channel.send(f"{message.author.mention} Cache cleared: {count} files removed.", delete_after=config.notification_timeout)
            else:
                await message.channel.send(f"{message.author.mention} " + get_feedback("admin_only"), delete_after=config.notification_timeout)

        elif command == "seek" and args:
            if radio.current_song:
                ts = args[0]
                try:
                    parts_ts = ts.split(":")
                    if len(parts_ts) == 2:
                        total = int(parts_ts[0]) * 60 + int(parts_ts[1])
                    else:
                        total = int(ts)
                    radio.dispatch(RadioAction.SEEK, total, user=message.author)
                    await message.channel.send(f"{message.author.mention} " + f"{t('jumping')} {ts}", delete_after=config.notification_timeout)
                except Exception:
                    await message.channel.send(f"{message.author.mention} " + get_feedback("format_error"), delete_after=config.notification_timeout)
            else:
                await message.channel.send(f"{message.author.mention} " + get_feedback("no_current_track"), delete_after=config.notification_timeout)

    except Exception as e:
        log.error(f"Error in prefix command {command}: {e}")
