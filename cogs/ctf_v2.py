import discord
from discord.ext import commands
from discord import Embed, utils
import datetime

class CTF(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Store message_id: {channel_id, participants set}
        self.ctf_announcements = {}

    @commands.command(name="ctf")
    async def announce_ctf(self, ctx, name: str, time: str, *, description: str):
        """Post a new CTF announcement and setup reactions."""

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        embed = Embed(
            title=f"📢 {name}",
            description=description,
            color=discord.Color.blue()
        )
        embed.add_field(name="🕒 Start Time (IST)", value=time, inline=False)
        embed.set_footer(text="React to join.")

        # Send announcement
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        await msg.add_reaction("🤔")

        # Create a private text channel
        guild = ctx.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        channel_name = name.lower().replace(" ", "-")
        ctf_channel = await guild.create_text_channel(channel_name, overwrites=overwrites)

        # Store the announcement mapping
        self.ctf_announcements[msg.id] = {
            "channel_id": ctf_channel.id,
            "participants": set()
        }

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        message_id = reaction.message.id
        emoji = str(reaction.emoji)

        if message_id not in self.ctf_announcements:
            return

        if emoji not in ["✅", "🤔"]:
            return

        guild = reaction.message.guild
        channel_id = self.ctf_announcements[message_id]["channel_id"]
        channel = guild.get_channel(channel_id)

        await channel.set_permissions(user, read_messages=True, send_messages=True)
        self.ctf_announcements[message_id]["participants"].add(user.id)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.bot:
            return

        message_id = reaction.message.id
        emoji = str(reaction.emoji)

        if message_id not in self.ctf_announcements:
            return

        if emoji not in ["✅", "🤔"]:
            return

        channel_id = self.ctf_announcements[message_id]["channel_id"]
        guild = reaction.message.guild
        channel = guild.get_channel(channel_id)

        await channel.set_permissions(user, overwrite=None)
        self.ctf_announcements[message_id]["participants"].discard(user.id)

async def setup(bot):
    await bot.add_cog(CTF(bot))
