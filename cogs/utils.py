import discord
import aiosqlite
from typing import Tuple, Union
from discord.ext import commands
from utils.helper import Spotify
from utils.scraper import Scraper
from utils.buttons import SetupButtons, SpotifyButton, ButtonPaginator


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

    @_setup.error
    async def _setup_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            perms = error.missing_permissions
            formatted_perms = ', '.join([' '.join(x.split('_')) for x in perms])
            return await ctx.send(f"You are missing **{formatted_perms}** to use this command!")
    
    @commands.command()
    @commands.cooldown(1, 5.0, commands.BucketType.user)
    async def suggestanime(self, ctx: commands.Context, amount: int = 1):
        if amount > 5:
            return await ctx.send("Can\'t request 5 links at once!")
        anime_class = Scraper(session=self.bot.session, amount=amount)
        anime = await anime_class.connect()
        if len(anime) > 1:
            final_embed_list = []
            for number in range(0, amount):
                embed = discord.Embed(color=self.bot.theme)
                embed.set_thumbnail(url=anime[number].cover)
                embed.description = f"""
                **__Name__**: {anime[number].name.title()} ({anime[number].type})

                **__Synopsis__**: {anime[number].description}

                **__Age Rating__**: {anime[number].age_rating}
                **__Rating__**: {anime[number].rating}
                **__Total Episodes__**: {anime[number].episodes}
                """
                embed.set_footer(text=f"{number+1}/{amount}")
                final_embed_list.append(embed)
            view = ButtonPaginator(ctx=ctx, list_to_paginate=final_embed_list)
            view.message = await ctx.send(embed=final_embed_list[0], view=view)
        else:
            anime = anime[0]
            embed = discord.Embed(color=self.bot.theme)
            embed.set_thumbnail(url=anime.cover)
            embed.description = f"""
            **__Name__**: {anime.name.title()} ({anime.type})

            **__Synopsis__**: {anime.description}

            **__Age Rating__**: {anime.age_rating}
            **__Rating__**: {anime.rating}
            **__Total Episodes__**: {anime.episodes}
            """
            await ctx.send(embed=embed)

    @suggestanime.error
    async def on_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandOnCooldown):
            time_left = round(error.retry_after, 1)
            return await ctx.send(f"You are using the command way too fast! Please try again after {time_left} Seconds")
        elif isinstance(error, commands.BadArgument):
            return await ctx.send(f"An Incorrect Argument was passed, use `{ctx.prefix}help {ctx.command.name}` for more info!")

    @commands.command(aliases=['sp'])
    @commands.cooldown(5, 60.0, type=commands.BucketType.user)
    async def spotify(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        async with ctx.typing():
            spotify = Spotify(bot=self.bot, member=member)
            embed = await spotify.get_embed()
            if not embed:
                if member == ctx.author:
                    return await ctx.reply(f"You are currently not listening to spotify!", mention_author=False)
                return await ctx.reply(f"{member.mention} is not listening to Spotify", mention_author=False,
                                       allowed_mentions=discord.AllowedMentions(users=False))
            activity = discord.utils.find(lambda act: isinstance(act, discord.Spotify), member.activities)
            view = SpotifyButton(ctx, activity)
            view.message = await ctx.send(embed=embed[0], file=embed[1], view=view)


def setup(bot):
    bot.add_cog(Utility(bot))