import asyncio
import discord
import aiosqlite
from typing import Optional
from utils.helper import Cache
from discord.ext import commands

class SpotifyButton(discord.ui.View):
    def __init__(self, ctx: commands.Context, act: discord.Spotify, *, timeout: Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.add_item(
            discord.ui.Button(label='Listen On Spotify', url=act.track_url, emoji="<:Spotify:919727284066336789>"))
        self.act = act
        self.context = ctx
        self.author = ctx.author

    async def on_timeout(self):
        self.deletembed.disabled = True
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.author:
            return True
        else:
            em = discord.Embed(title="Begone!",
                               description=f"This is not yours, only **`{self.author.name}`** can use this button.")
            await interaction.response.send_message(embed=em, ephemeral=True)
            return False

    @discord.ui.button(emoji="🗑️", label="Close Embed", style=discord.ButtonStyle.red)
    async def deletembed(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.message.delete()


class ButtonDelete(discord.ui.View):
    __slots__ = ('context',)

    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.context = ctx

    async def on_timeout(self):
        self.clear_items()
        # await self.message.edit(view=self)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.context.author.id:
            return True
        checkmbed = discord.Embed(
            colour=0x2F3136,
            description=f"{interaction.user.mention}, Only {self.context.author.mention} can use this.",
            timestamp=self.context.message.created_at
        )
        await interaction.response.send_message(embed=checkmbed, ephemeral=True)
        return False

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.gray)
    async def buttondelete(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.context.message.add_reaction("☑️")
        await interaction.message.delete()

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


class ButtonPaginator(discord.ui.View):
    def __init__(self, *, ctx: commands.Context, list_to_paginate: list, timeout: Optional[float] = 60):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.list = list_to_paginate
        self.pointer = 0

    def check_back(self):
        if self.pointer == 0:
            return False
        self.pointer = self.pointer - 1
        return True
    
    def check_next(self):
        if self.pointer == len(self.list) - 1:
            return False
        self.pointer = self.pointer + 1
        return True

    def disable_one_side(self, side: str):
        if side == 'left':
            self.first.disabled = True
            self.back.disabled = True
            self.next.disabled = False
            self.last.disabled = False
        elif side == 'right':
            self.next.disabled = True
            self.last.disabled = True
            self.back.disabled = False
            self.first.disabled = False
    
    def disable_or_enable_all(self, value: bool):
        for view in self.children:
            view.disabled = value
            
    async def on_timeout(self) -> None:
        self.disable_or_enable_all(True)
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.ctx.author == interaction.user:
            return True
        else:
            embed = discord.Embed(title="Not your embed", description=f"Only {self.ctx.author} can use this button")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
    
    @discord.ui.button(emoji="⏪", disabled=True)
    async def first(self, button: discord.Button, interaction: discord.Interaction):
        if self.pointer == 0:
            return
        self.pointer = 0
        self.disable_one_side('left')
        await interaction.message.edit(embed=self.list[0], view=self)

    @discord.ui.button(emoji="◀️", disabled=True)
    async def back(self, button: discord.Button, interaction: discord.Interaction):
        handshake = self.check_back()
        if handshake:
            self.disable_or_enable_all(False)
            if self.pointer == 0:
                self.disable_one_side('left')
            await interaction.message.edit(embed=self.list[self.pointer], view=self)

    @discord.ui.button(emoji="🗑️")
    async def delete(self, button: discord.Button, interaction: discord.Interaction):
        await interaction.message.delete()

    @discord.ui.button(emoji="▶️")
    async def next(self, button: discord.Button, interaction: discord.Interaction):
        handshake = self.check_next()
        if handshake:
            self.disable_or_enable_all(False)
            if self.pointer == len(self.list) - 1:
                self.disable_one_side('right')
            await interaction.message.edit(embed=self.list[self.pointer], view=self)

    @discord.ui.button(emoji="⏩")
    async def last(self, button: discord.Button, interaction: discord.Interaction):
        if self.pointer == len(self.list) - 1:
            return
        self.pointer = len(self.list) - 1
        self.disable_one_side('right')
        await interaction.message.edit(embed=self.list[-1], view=self)

        
        




