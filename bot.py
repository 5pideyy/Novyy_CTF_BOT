import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# Load extensions (cogs)
#bot.load_extension("cogs.ctf")
async def main():
    await bot.load_extension("cogs.ctf")
    await bot.start(TOKEN)

import asyncio
asyncio.run(main())


bot.run(TOKEN)
