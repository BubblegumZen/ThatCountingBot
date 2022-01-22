from genericpath import exists
import discord
import aiosqlite
from typing import Tuple, Union
from discord.ext import commands
from utils.buttons import SetupButtons

class Utility(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.text_channel = "<:text_channel:933039916961656904>"
        self.count = "🔢"

    async def update_info(self, *updates):
        to_update_possible = {'channel': 'channel_id', 'author': 'author_id', 'count': 'count'}
        to_update = [to_update_possible[x] for x in updates]
        argument = ", ".join(to_update)
        return argument

    async def fetch_info(self, guild_id: int) -> Union[Tuple[int,int], None]:
        async with aiosqlite.connect('./databases/count.db') as conn:
            async with conn.cursor() as cursor:
                record_cursor = await cursor.execute("SELECT channel_id, count FROM guilds WHERE guild_id = ?", (guild_id,))
                records = await record_cursor.fetchone()
        return records # None | (int, int)

    @commands.command(name="setup")
    @commands.has_permissions(manage_guild=True)
    async def _setup(self, ctx: commands.Context, *flags):
        if '--existing' in flags:
            existing = True
        else:
            existing = False
        choices = {0: f'{self.text_channel} Channel:' + ' {}', 1: f'{self.count} Count:' + ' {}'}
        records = await self.fetch_info(ctx.guild.id)
        if not records:
            format_variables = ("None", "None")
        else:
            channel_id, count = records
            channel = await self.bot.get_or_fetch_guild_entity(channel_id, ctx.guild.id, 'channel')
            channel_formatted = channel.mention if channel else "#deleted-channel"
            current_count = str(count)
            format_variables = (channel_formatted, current_count)
        formatted_string = "\n".join([f"{value.title().format(format_variables[count])}" for count, value in choices.items()])
        embed = discord.Embed(title="Current Configurations", description=formatted_string, color=self.bot.theme)
        view = SetupButtons(ctx, existing=existing)
        await ctx.send(embed=embed, view=view)



def setup(bot):
    bot.add_cog(Utility(bot))