import discord
from discord.ext import commands, tasks
from discord import Embed
from datetime import datetime, timedelta, timezone
from dateutil import parser
from pytz import timezone as pytz_timezone
import re

class Color:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def debug_print(tag: str, message: str, color: str = Color.OKBLUE):
    print(f"{color}[{tag}]{Color.ENDC} {message}")

class CTFView(discord.ui.View):
    def __init__(self, cog, message_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.message_id = message_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return not interaction.user.bot

    async def handle_response(self, interaction: discord.Interaction, emoji: str):
        user = interaction.user
        data = self.cog.ctf_announcements.get(self.message_id)
        if not data:
            return await interaction.response.send_message("CTF data missing or expired.", ephemeral=True)

        if data["locked"] and emoji in ["✅", "🤔"]:
            return await interaction.response.send_message("⛔ Reactions locked 30 mins before start.", ephemeral=True)

        for e in ["✅", "❌", "🤔"]:
            data["participants"][e].discard(user.id)

        data["participants"][emoji].add(user.id)

        channel = interaction.guild.get_channel(data["channel_id"])
        if emoji in ["✅", "🤔"]:
            await channel.set_permissions(user, read_messages=True, send_messages=True)
        else:
            await channel.set_permissions(user, overwrite=None)

        await self.cog.update_embed(self.message_id)
        await interaction.response.defer()

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="ctf_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_response(interaction, "✅")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="ctf_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_response(interaction, "❌")

    @discord.ui.button(label="Tentative", style=discord.ButtonStyle.secondary, custom_id="ctf_tentative")
    async def tentative(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_response(interaction, "🤔")

class CTF(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctf_announcements = {}
        self.check_ctf_timers.start()
        debug_print("INIT", "CTF Cog loaded and timer started.", Color.OKGREEN)

    @commands.command(name="ctf")
    async def announce_ctf(self, ctx, name: str, range_str: str, *, description: str):
        required_role_id = 1385239398718902403
        if not any(role.id == required_role_id for role in ctx.author.roles):
            await ctx.send("❌ You do not have permission to use this command.")
            debug_print("AUTH", f"Unauthorized attempt by {ctx.author.display_name}", Color.FAIL)
            return

        try:
            await ctx.message.delete()
            debug_print("COMMAND", f"Deleted user command message: {ctx.message.content}", Color.OKCYAN)
        except discord.Forbidden:
            debug_print("WARN", "Missing permission to delete user message.", Color.WARNING)

        try:
            parts = re.split(r"\s+[\u2013\u2014\-]{1,2}\s+", range_str)
            if len(parts) != 2:
                raise ValueError("Date range must contain exactly two dates separated by a dash")

            ist = pytz_timezone("Asia/Kolkata")
            start_naive = parser.parse(parts[0], ignoretz=True)
            end_naive = parser.parse(parts[1], ignoretz=True)

            start_dt = ist.localize(start_naive)
            end_dt = ist.localize(end_naive)

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

        view = CTFView(self, msg.id)
        await msg.edit(view=view)
        debug_print("BUTTONS", f"Added UI buttons to message {msg.id}", Color.OKGREEN)

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
                archive_category = discord.Object(id=1379020840879915048)
                await channel.send("@here 📦 Archiving this channel .")
                await channel.edit(category=archive_category, sync_permissions=True)
                del self.ctf_announcements[msg_id]
                debug_print("ARCHIVE", f"Moved CTF channel {channel.name} to archive category", Color.WARNING)

    @check_ctf_timers.before_loop
    async def before_timer(self):
        await self.bot.wait_until_ready()
        debug_print("TASK", "Timer waiting for bot ready...", Color.OKGREEN)

async def setup(bot):
    await bot.add_cog(CTF(bot))
    debug_print("SETUP", "CTF cog setup complete.", Color.OKGREEN)
