import asyncio
from code import interact
import discord
import aiosqlite
from typing import Optional
from utils.helper import Cache
from discord.ext import commands



class SetupButtons(discord.ui.View):
    def __init__(self, ctx: commands.Context, *, existing: bool, timeout: Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.ctx: commands.Context = ctx
        self.count: str = "🔢"
        self.text_channel: str = "<:text_channel:933039916961656904>"
        self._existing = existing

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.ctx.author == interaction.user:
            return True
        else:
            embed = discord.Embed(title="Not your embed", description=f"Only {self.ctx.author} can use this button")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False

    def check_for_cache(self, guild_id):
        if guild_id in self.ctx.bot.cache:
            return self.ctx.bot.cache[guild_id]
        return None

    async def push_update(self, to_update, *args): # args  = guild_id, channel_id | guild_id, count 
        async with aiosqlite.connect('./databases/count.db') as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('''INSERT INTO guilds(guild_id, {0}) VALUES(?, ?)
                                        ON CONFLICT(guild_id) DO UPDATE SET {0} = ?'''.format(to_update), args)
            await conn.commit()
        available = self.check_for_cache(args[0])
        if available:
            if available.count is None:
                available.count = {to_update: args[1], 'count': 0}
            else:
                available.count[to_update] = args[1]
        else:
            to_insert = Cache({to_update: args[1]})
            self.ctx.bot.cache[args[0]] = to_insert
        

    @discord.ui.button(label="Set Channel", emoji="<:text_channel:933039916961656904>", style=discord.ButtonStyle.blurple)
    async def channel_setup(self, button: discord.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.followup.send("Please send the channel you want to set as your counting channel", ephemeral=True)
        def check(message):
            return message.author == interaction.user and message.channel == interaction.channel
        condition = True
        while condition:
            try:
                response = await self.ctx.bot.wait_for('message', check=check, timeout=45)
            except asyncio.TimeoutError:
                return await interaction.followup.send("You did not respond in time, aborting the process", ephemeral=True)
            else:
                try:
                    channel = await commands.TextChannelConverter().convert(self.ctx, response.content)
                except commands.ChannelNotFound as e:
                    print(e)
                    continue
                await self.push_update('channel_id', self.ctx.guild.id, channel.id, channel.id)
                if self._existing:
                    history = await channel.history(limit=10).flatten()
                    history_parser = [count_number for count_number in history if count_number.content.isdigit()]
                    current_checkmark = history_parser[0]
                    await self.push_update('count', self.ctx.guild.id, int(current_checkmark.content), int(current_checkmark.content))
                embed = discord.Embed(description=f"Successfully set channel to {channel.mention}")
                return await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Set Current Count", emoji="🔢", style=discord.ButtonStyle.blurple)
    async def count_setup(self, button: discord.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.followup.send("Please send the number you wish to set current count on", ephemeral=True)
        def check(message):
            return message.author == interaction.user and message.channel == interaction.channel and message.content.isdigit()
        condition = True
        while condition:
            try:
                response = await self.ctx.bot.wait_for('message', check=check, timeout=45)
            except asyncio.TimeoutError:
                return await interaction.followup.send("You did not respond in time, aborting the process", ephemeral=True)
            else:
                number = int(response.content)
                if number > 1e25:
                    await interaction.followup.send("Number is too big!")
                    continue
                await self.push_update('count', self.ctx.guild.id, number, number)
                embed = discord.Embed(description=f"Successfully set current count to {number}")
                return await interaction.followup.send(embed=embed, ephemeral=True)



