import discord
from discord.ext import commands
from discord.utils import get
import asyncio
from utils.archive import schedule_archive

class CTF(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctf_message_id = None
        self.ctf_name = None
        self.ctf_participants = {"✅": set(), "🤔": set()}
        self.ctf_list = []

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ctf(self, ctx, name: str, time: str, *, description: str):
        self.ctf_name = name
        embed = discord.Embed(title=f"CTF: {name}", description=description, color=0x3498db)
        embed.add_field(name="Time (IST)", value=time)
        embed.set_footer(text="React with ✅ to Accept, ❌ to Reject, 🤔 for Tentative")

        role = get(ctx.guild.roles, name="CTFPlayers")
        if role:
            await ctx.send(f"{role.mention} New CTF posted!")

        message = await ctx.send(embed=embed)
        self.ctf_message_id = message.id

        for emoji in ["✅", "❌", "🤔"]:
            await message.add_reaction(emoji)

        self.ctf_list.append({"name": name, "time": time, "desc": description})

    @commands.command()
    async def ctfs(self, ctx):
        if not self.ctf_list:
            await ctx.send("No active CTFs.")
            return

        embed = discord.Embed(title="📅 Upcoming CTFs", color=0x2ecc71)
        for ctf in self.ctf_list:
            embed.add_field(name=ctf["name"], value=f"{ctf['desc']} (⏰ {ctf['time']})", inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def archive(self, ctx, *, ctf_name: str):
        channel_name = ctf_name.lower().replace(" ", "-")
        channel = get(ctx.guild.channels, name=channel_name)
        if channel:
            await channel.edit(name=f"archived-{channel_name}")
            await channel.set_permissions(ctx.guild.default_role, read_messages=False)
            await ctx.send(f"✅ Archived {channel.mention}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.message_id != self.ctf_message_id:
            return
        if payload.emoji.name not in ["✅", "🤔"]:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member.bot:
            return

        self.ctf_participants[payload.emoji.name].add(member)

        channel_name = self.ctf_name.lower().replace(" ", "-")
        existing = get(guild.channels, name=channel_name)
        if not existing:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False)
            }
            for user in self.ctf_participants["✅"].union(self.ctf_participants["🤔"]):
                overwrites[user] = discord.PermissionOverwrite(read_messages=True)
            new_channel = await guild.create_text_channel(channel_name, overwrites=overwrites)
            await schedule_archive(new_channel)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.message_id != self.ctf_message_id:
            return
        if payload.emoji.name not in ["✅", "🤔"]:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        channel = get(guild.channels, name=self.ctf_name.lower().replace(" ", "-"))

        if member and channel:
            await channel.set_permissions(member, overwrite=None)
            self.ctf_participants[payload.emoji.name].discard(member)

async def setup(bot):
    await bot.add_cog(CTF(bot))
