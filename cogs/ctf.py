import discord
from discord.ext import commands
from discord import Embed
import datetime

class CTF(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctf_announcements = {}  # message_id -> {channel_id, participants: {"✅": set(), "❌": set(), "🤔": set()}, message}

    @commands.command(name="ctf")
    async def announce_ctf(self, ctx, name: str, time: str, *, description: str):
        """Post a new CTF announcement and setup reactions."""
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        embed = Embed(
            title=f" {name}",
            description=description,
            color=discord.Color.blurple()
        )
        embed.add_field(name="  Start Time (IST)", value=time, inline=False)
        embed.add_field(name="✅ Accepted", value="No one yet", inline=True)
        embed.add_field(name="❌ Rejected", value="No one yet", inline=True)
        embed.add_field(name="🤔 Tentative", value="No one yet", inline=True)
        embed.set_footer(text="React below to join or ignore.")

        msg = await ctx.send(embed=embed)

        for emoji in ["✅", "❌", "🤔"]:
            await msg.add_reaction(emoji)

        guild = ctx.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }

        channel_name = name.lower().replace(" ", "-")
        category = ctx.channel.category
        ctf_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category)

        self.ctf_announcements[msg.id] = {
            "channel_id": ctf_channel.id,
            "participants": {
                "✅": set(),
                "❌": set(),
                "🤔": set()
            },
            "message": msg
        }

    async def update_embed(self, message_id):
        data = self.ctf_announcements.get(message_id)
        if not data:
            return

        msg = data["message"]
        embed = msg.embeds[0]

        for emoji in ["✅", "❌", "🤔"]:
            users = data["participants"][emoji]
            display = "\n".join(users) if users else "No one yet"

            for i, field in enumerate(embed.fields):
                if field.name.startswith(emoji):
                    embed.set_field_at(i, name=field.name, value=display, inline=True)

        await msg.edit(embed=embed)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot or reaction.message.id not in self.ctf_announcements:
            return

        emoji = str(reaction.emoji)
        if emoji not in ["✅", "❌", "🤔"]:
            return

        data = self.ctf_announcements[reaction.message.id]

        # Remove user from all other categories
        for status in ["✅", "❌", "🤔"]:
            data["participants"][status].discard(user.display_name)

        # Add user to the selected category
        data["participants"][emoji].add(user.display_name)

        # Give channel access if accepted or tentative
        if emoji in ["✅", "🤔"]:
            guild = reaction.message.guild
            channel = guild.get_channel(data["channel_id"])
            await channel.set_permissions(user, read_messages=True, send_messages=True)

        await self.update_embed(reaction.message.id)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.bot or reaction.message.id not in self.ctf_announcements:
            return

        emoji = str(reaction.emoji)
        if emoji not in ["✅", "❌", "🤔"]:
            return

        data = self.ctf_announcements[reaction.message.id]
        data["participants"][emoji].discard(user.display_name)

        # Remove access if it's from an access-granting reaction
        if emoji in ["✅", "🤔"]:
            guild = reaction.message.guild
            channel = guild.get_channel(data["channel_id"])
            await channel.set_permissions(user, overwrite=None)

        await self.update_embed(reaction.message.id)

async def setup(bot):
    await bot.add_cog(CTF(bot))
