import asyncio

async def schedule_archive(channel, hours=1000):
    await asyncio.sleep(hours * 3600)
    await channel.edit(name=f"archived-{channel.name}")
    await channel.set_permissions(channel.guild.default_role, read_messages=False)
