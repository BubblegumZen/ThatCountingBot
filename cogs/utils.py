import re
import enum
import discord
import datetime
import aiosqlite
from utils.scraper import Scraper
from utils.helper import Spotify, Cache
from discord.ext import commands, tasks
from typing import Optional, Tuple, Union
from utils.buttons import SetupButtons, SpotifyButton, ButtonPaginator, ConfigSetupButtons, AlertButton

class Violation(enum.Enum):
    GUARANTEED = "Posted a registered malicious Scam Link ([`repo`](https://github.com/nikolaischunk/discord-phishing-links/blob/main/domain-list.json))" # HANDLES
    MESSAGE_VIOLATION = "Posted same message in multiple channels: {}" # HANDLES


class Utility(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.alert_role = "<:alert:937249118399647766>"
        self.text_channel = "<:text_channel:933039916961656904>"
        self.check_and_reset.start()
        self.count = "🔢"

    @tasks.loop(seconds=60)
    async def check_and_reset(self):
        current_time = datetime.datetime.utcnow()
        for key in self.bot.cache.copy():
            cached = self.bot.cache[key].anti_raid_limit
            if cached:
                for modifiable_key, value in cached.copy().items():
                    if (current_time.replace(tzinfo=None) - value[0][1][-1].created_at.replace(tzinfo=None)).total_seconds() > 300:
                        del cached[modifiable_key]


    @staticmethod
    async def create_table(cursor, conn):
        await cursor.execute(
            '''CREATE TABLE guilds(
            guild_id INTEGER UNIQUE, 
            role_id INTEGER DEFAULT 0,
            channel_id INTEGER DEFAULT 0,
            prefix TEXT DEFAULT null
            )''')
        await conn.commit()

    async def fetch_info_count(self, guild_id: int) -> Union[Tuple[int,int], None]:
        async with self.bot.count_conn.cursor() as cursor:
            record_cursor = await cursor.execute("SELECT channel_id, count FROM guilds WHERE guild_id = ?", (guild_id,))
            records = await record_cursor.fetchone()
        return records # None | (int, int)

    async def fetch_info_config(self, guild_id: int) -> Union[Tuple[int,int], None]:
        async with self.bot.config_conn.cursor() as cursor:
            try:
                record_cursor = await cursor.execute("SELECT channel_id, role_id FROM guilds WHERE guild_id = ?", (guild_id,))
            except aiosqlite.OperationalError:
                await self.create_table(cursor, self.bot.config_conn)
                record_cursor = await cursor.execute("SELECT channel_id, role_id FROM guilds WHERE guild_id = ?", (guild_id,))
            records = await record_cursor.fetchone()
        return records # None | (int, int)

    def check_for_cache(self, guild_id):
        if guild_id in self.bot.cache:
            return self.bot.cache[guild_id]
        return None
    
    async def send_alert(self, message: discord.Message, channel_id: int, role_id: Optional[int], *, violation: Violation):
        channel = message.guild.get_channel(channel_id)
        if channel:
            reason = violation.value
            if violation is violation.MESSAGE_VIOLATION:
                arg = f"\n**Content**: {message.content}"
                reason = reason.format(arg)
            role = message.guild.get_role(role_id)
            if role:
                content = role.mention if role != message.guild.default_role else role.name
            else:
                content = None
            view = AlertButton(self.bot, message)
            embed = discord.Embed(title="Likely a spam", 
                                  description=f"**Username**: {message.author.display_name}\n**User ID**: (`{message.author.id}`)\n**Channel Violation Raised**: {message.channel.mention}\n**Violation**: {reason}",
                                  color=self.bot.theme,
                                  timestamp=message.created_at)
            embed.set_footer(text="Please take a few minutes to confirm this before choosing an action", icon_url=self.bot.user.avatar.url)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            await channel.send(content=content, embed=embed, view=view)

    def record_suspicious_link(self, link: str):
        with open('./Assets/Links/write_file.txt', 'a') as file:
            file.write(link + "\n")

    def find_link(self, message: discord.Message, *args) -> bool:
        regex = r"(?:(?:https?|ftp):\/\/|\b(?:[a-z\d]+\.))(?:(?:[^\s()<>]+|\((?:[^\s()<>]+|(?:\([^\s()<>]+\)))?\))+(?:\((?:[^\s()<>]+|(?:\(?:[^\s()<>]+\)))?\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))?"
        match = re.search(regex, message.content)
        if match:
            content = message.content.lower()
            grouping = match.group(0)
            if grouping.startswith("https://"):
                domain = grouping.split('https://')[1]
            elif grouping.startswith('http://'):
                domain = grouping.split('http://')[1]
            else:
                domain = grouping
            domain = domain.split('/')[0]
            if domain in self.bot.cache_suspicious_links:
                loop = self.bot.loop
                loop.create_task(self.send_alert(message, *args, violation=Violation.GUARANTEED))
            elif "nitro" in content or "free nitro" in content or "free steam" in content or "free" in content:
                self.record_suspicious_link(grouping)
            return True
        return False

    def delete_or_add(self, cache: Cache, message: discord.Message, *args):
        cached_object = cache.anti_raid_limit
        if message.author.id in cached_object:
            if message.content == cached_object[message.author.id][0][1][-1].content and not message.attachments:
                distinct_channels = len(set([x.channel for x in cached_object[message.author.id][0][1]]))
                if (distinct_channels/len(message.guild.text_channels))*100 < 50:
                    cached_object[message.author.id][0][0] += 1
                    cached_object[message.author.id][0][1].append(message)
                    if self.find_link(message, *args):
                        cached_object[message.author.id][1] += 1
                else:
                    loop = self.bot.loop
                    loop.create_task(self.send_alert(message, *args, violation=Violation.MESSAGE_VIOLATION))
                    del cached_object[message.author.id]
            else:
                del cached_object[message.author.id]
        else:
            cached_object[message.author.id] = [[1, [message]], int(self.find_link(message, *args))]
               

    @commands.Cog.listener('on_message')
    async def anti_spam(self, message: discord.Message):
        """
        problem 1:
            message identification: 
                can store full message, inefficient
            useless doubt, store message object only instead of datetime.datetime
            ?
        {id: (number, [(Message, datetime.datetime)])} -> {id: [(number, [Message]), link_limit]} # Message.created_at
        if last message was sent > 5 mins ago, delete entry
        if current message is different from last message, delete entry
        if consecutive messages that are the same are sent in different channels of a guild, 
        which satisfies (total channels sent on)/(len(guild.text_channels))*100 > 50, alert
        # requires permissions to:
            mention roles
            or
            moderate members
            or
            ban/kick users
                this depends on the configuration made by admins of the server
        if consecutive messages sent over different channels contain the same link, alert
        if consecutive messages sent over different channels contains any suspcious link, 
        documented in:
                    https://github.com/BuildBot42/discord-scam-links/blob/main/list.txt
        alert.
        """
        if message.author.bot:
            return
        records = await self.fetch_info_config(message.guild.id)
        if not records:
            return
        cached_object = self.check_for_cache(message.guild.id)
        if cached_object:
            if not cached_object.anti_raid_limit:
                cached_object.anti_raid_limit = {message.author.id: [[1, [message]], int(self.find_link(message, *records))]}
            else:
                self.delete_or_add(cached_object, message, *records)
        else:
            self.bot.cache[message.guild.id] = Cache()


    @commands.command(name="serverconfig", aliases=['rsetup, config'])
    @commands.has_permissions(manage_guild=True)
    async def __setup(self, ctx: commands.Context):
        choices = {0: f'{self.text_channel} Logging Channel:' + ' {}', 1: f' {self.alert_role} Alert Role:' + ' {}'}
        records = await self.fetch_info_config(ctx.guild.id)
        if not records:
            format_variables = ("None", "None")
        else:
            channel_id, role_id = records
            channel = await commands.GuildChannelConverter().convert(ctx, str(channel_id))
            channel_formatted = channel.mention if channel else "#deleted-channel"
            role = await commands.RoleConverter().convert(ctx, str(role_id))
            role_formatted = role.mention if role else "@deleted-role"
            if role == ctx.guild.default_role:
                role_formatted = role.name
            format_variables = (channel_formatted, role_formatted)
        formatted_string = "\n".join([f"{value.title().format(format_variables[count])}" for count, value in choices.items()])
        embed = discord.Embed(title="Current Configurations", description=formatted_string, color=self.bot.theme)
        view = ConfigSetupButtons(ctx)
        await ctx.send(embed=embed, view=view)


    @commands.command(name="setup")
    @commands.has_permissions(manage_guild=True)
    async def _setup(self, ctx: commands.Context, *flags):
        if '--existing' in flags:
            existing = True
        else:
            existing = False
        choices = {0: f'{self.text_channel} Channel:' + ' {}', 1: f'{self.count} Count:' + ' {}'}
        records = await self.fetch_info_count(ctx.guild.id)
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
            formatted_perms = ', '.join([' '.join(x.split('_')).title() for x in perms])
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