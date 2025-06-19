import discord
from discord.ext import commands, tasks
from discord import Embed
from datetime import datetime, timedelta, timezone
from dateutil import parser
from pytz import timezone as pytz_timezone
import re

class Color:
    HEADER = '\033[95m'      # Purple
    OKBLUE = '\033[94m'      # Blue
    OKCYAN = '\033[96m'      # Cyan
    OKGREEN = '\033[92m'     # Green
    WARNING = '\033[93m'     # Yellow
    FAIL = '\033[91m'        # Red
    ENDC = '\033[0m'         # Reset
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def debug_print(tag: str, message: str, color: str = Color.OKBLUE):
    print(f"{color}[{tag}]{Color.ENDC} {message}")


class CTF(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctf_announcements = {}  # message_id -> data
        self.check_ctf_timers.start()
        debug_print("INIT", "CTF Cog loaded and timer started.", Color.OKGREEN)
    def parse_datetime_string(self, dt_string: str):
        cleaned = dt_string.strip().replace("IST", "").strip()
        naive_dt = parser.parse(cleaned)
        ist = pytz_timezone("Asia/Kolkata")
        return ist.localize(naive_dt).astimezone(timezone.utc)

    @commands.command(name="ctf")
    async def announce_ctf(self, ctx, name: str, range_str: str, *, description: str):
        """Post a new CTF announcement with start and end time."""
        try:
            await ctx.message.delete()
            debug_print("COMMAND", f"Deleted user command message: {ctx.message.content}", Color.OKCYAN)
        except discord.Forbidden:
            debug_print("WARN", "Missing permission to delete user message.", Color.WARNING)

        try:
            # Example: 'Fri, 20 June 2025, 15:30 IST — Sun, 22 June 2025, 03:30 IST'
            parts = re.split(r"\s+[\u2013\u2014\-]{1,2}\s+", range_str)
            if len(parts) != 2:
                raise ValueError("Date range must contain exactly two dates separated by a dash")

            ist = pytz_timezone("Asia/Kolkata")
            start_dt_raw = parser.parse(parts[0])
            end_dt_raw = parser.parse(parts[1])

            # Only localize if not already timezone-aware
            start_dt = start_dt_raw if start_dt_raw.tzinfo else ist.localize(start_dt_raw)
            end_dt = end_dt_raw if end_dt_raw.tzinfo else ist.localize(end_dt_raw)

            start_dt = start_dt.astimezone(timezone.utc)
            end_dt = end_dt.astimezone(timezone.utc)

            debug_print("TIME", f"Parsed start: {start_dt}, end: {end_dt}", Color.OKCYAN)
        except Exception as e:
            await ctx.send(f"❌ Error parsing dates: `{e}`. Format: `Sat, 21 June 2025, 12:30 IST — Sun, 22 June 2025, 12:30 IST`")
            debug_print("ERROR", f"Failed to parse dates: {e}", Color.FAIL)
            return

        embed = Embed(title=f"{name}", description=description, color=discord.Color.blurple())
        embed.add_field(name="  Start Time", value=f"<t:{int(start_dt.timestamp())}:F> (<t:{int(start_dt.timestamp())}:R>)", inline=False)
        embed.add_field(name="  End Time", value=f"<t:{int(end_dt.timestamp())}:F>", inline=False)
        embed.add_field(name="✅ Accepted", value="No one yet", inline=True)
        embed.add_field(name="❌ Rejected", value="No one yet", inline=True)
        embed.add_field(name="🤔 Tentative", value="No one yet", inline=True)
        embed.set_footer(text="Powered by NOVA")

        try:
            msg = await ctx.send(embed=embed)
            debug_print("ANNOUNCE", f"Posted embed announcement: {msg.id}", Color.OKGREEN)
        except Exception as e:
            debug_print("ERROR", f"Failed to send embed: {e}", Color.FAIL)
            await ctx.send("Failed to post announcement.")
            return

        for emoji in ["✅", "❌", "🤔"]:
            await msg.add_reaction(emoji)
            debug_print("REACTION", f"Added reaction: {emoji}", Color.OKBLUE)

        guild = ctx.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        channel_name = re.sub(r"[^a-z0-9\-]", "", name.lower().replace(" ", "-"))
        category = ctx.channel.category
        ctf_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category)
        debug_print("CHANNEL", f"Created private CTF channel: {ctf_channel.name} ({ctf_channel.id})", Color.OKGREEN)

        self.ctf_announcements[msg.id] = {
            "channel_id": ctf_channel.id,
            "participants": {"✅": set(), "❌": set(), "🤔": set()},
            "message": msg,
            "start_time": start_dt,
            "end_time": end_dt,
            "pinged_30min": False,
            "pinged_start": False,
            "locked": False
        }
        debug_print("STATE", f"CTF announcement tracked under ID: {msg.id}", Color.HEADER)

    async def update_embed(self, message_id):
        data = self.ctf_announcements.get(message_id)
        if not data:
            debug_print("UPDATE", f"No data found for message ID: {message_id}", Color.WARNING)
            return

        msg = data["message"]
        embed = msg.embeds[0]

        for emoji in ["✅", "❌", "🤔"]:
            users = data["participants"][emoji]
            display = "\n".join(f"<@{uid}>" for uid in users) if users else "No one yet"

            for i, field in enumerate(embed.fields):
                if field.name.startswith(emoji):
                    embed.set_field_at(i, name=field.name, value=display, inline=True)

        await msg.edit(embed=embed)
        debug_print("UPDATE", f"Updated embed for message ID: {message_id}", Color.OKBLUE)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot or reaction.message.id not in self.ctf_announcements:
            return

        emoji = str(reaction.emoji)
        if emoji not in ["✅", "❌", "🤔"]:
            return

        data = self.ctf_announcements[reaction.message.id]

        if data.get("locked") and emoji in ["✅", "🤔"]:
            await reaction.message.remove_reaction(emoji, user)
            debug_print("LOCKED", f"Rejected reaction by {user} due to lock.", Color.WARNING)
            return

        for other in ["✅", "❌", "🤔"]:
            if other != emoji:
                await reaction.message.remove_reaction(other, user)
                data["participants"][other].discard(user.id)

        data["participants"][emoji].add(user.id)

        if emoji in ["✅", "🤔"]:
            guild = reaction.message.guild
            channel = guild.get_channel(data["channel_id"])
            await channel.set_permissions(user, read_messages=True, send_messages=True)

        await self.update_embed(reaction.message.id)
        debug_print("REACTION ADD", f"{user.display_name} reacted with {emoji}", Color.OKBLUE)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.bot or reaction.message.id not in self.ctf_announcements:
            return

        emoji = str(reaction.emoji)
        if emoji not in ["✅", "❌", "🤔"]:
            return

        data = self.ctf_announcements[reaction.message.id]
        data["participants"][emoji].discard(user.id)

        if emoji in ["✅", "🤔"]:
            guild = reaction.message.guild
            channel = guild.get_channel(data["channel_id"])
            await channel.set_permissions(user, overwrite=None)

        await self.update_embed(reaction.message.id)
        debug_print("REACTION REMOVE", f"{user.display_name} removed {emoji}", Color.OKBLUE)

    @tasks.loop(minutes=1)
    async def check_ctf_timers(self):
        now = datetime.now(timezone.utc)

        for msg_id, data in list(self.ctf_announcements.items()):
            channel = self.bot.get_channel(data["channel_id"])

            if not data["pinged_30min"] and now >= data["start_time"] - timedelta(minutes=30):
                await channel.send("@here ⏰ CTF starts in 30 minutes!")
                data["pinged_30min"] = True
                data["locked"] = True
                debug_print("PING", f"30-minute warning sent for CTF {channel.name}", Color.OKCYAN)

            if not data["pinged_start"] and now >= data["start_time"]:
                await channel.send("@here 🚩 CTF has started!")
                data["pinged_start"] = True
                debug_print("PING", f"Start notification sent for CTF {channel.name}", Color.OKCYAN)

            if now >= data["end_time"] + timedelta(hours=72):
                await channel.send("📦 Archiving this channel now.")
                await channel.edit(archived=True)
                del self.ctf_announcements[msg_id]
                debug_print("ARCHIVE", f"Archived CTF channel {channel.name} after 72h", Color.WARNING)

    @check_ctf_timers.before_loop
    async def before_timer(self):
        await self.bot.wait_until_ready()
        debug_print("TASK", "Timer waiting for bot ready...", Color.OKGREEN)


async def setup(bot):
    await bot.add_cog(CTF(bot))
    debug_print("SETUP", "CTF cog setup complete.", Color.OKGREEN)
