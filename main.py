import asyncio
import os
import sys
import json
import config
import uvloop
import logging
import aiohttp
import datetime
import humanize
import aiosqlite
import subprocess
from utils import helper
from typing import Optional, Tuple, Union

def clear_console():
    subprocess.check_call(['clear'])

def install_dependencies():
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
    clear_console()

install_dependencies()

import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True
intents.presences = True

class CountBot(commands.AutoShardedBot):
    COG_DISABLED = ['level.py']
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theme: int = 0xA8A5F1
        self.level_conn: aiosqlite.Connection = None
        self.count_conn: aiosqlite.Connection = None
        self.config_conn: aiosqlite.Connection = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.uptime: datetime.datetime = datetime.datetime.utcnow()
        self.formatted = self.uptime.strftime('%d %B %Y | %H:%M:%S')
        self.cache: dict = {}
        self.cache_suspicious_links: Optional[list] = None
        self.logger: logging.Logger = logging.getLogger('discord')
        self.logger.setLevel(logging.INFO)
        self.spotify_session: Optional[Tuple] = None
        self.spotify_client_id: str = config.SPOTIFY_CLIENT_ID
        self.spotify_client_secret: str = config.SPOTIFY_CLIENT_SECRET

    os.environ["JISHAKU_NO_DM_TRACEBACK"] = "False"
    os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
    os.environ["JISHAKU_HIDE"] = "True"
    os.environ["JISHAKU_RETAIN"] = "True"

    async def on_ready(self):
        print(bot.user.name, "is now ready!")

    # maybe remove
    async def get_or_fetch_bot_entity(self, snowflake: id, obj: str) -> Union[discord.User, discord.TextChannel, discord.VoiceChannel]:
        object_dict_list = {
            'channel': (self.get_channel, self.fetch_channel),
            'user': (self.get_user, self.fetch_user), 
        }
        action_to_take = object_dict_list.get(obj)
        to_return = action_to_take[0](snowflake)
        if not to_return:
            try:
                to_return = await action_to_take[1](snowflake)
            except discord.NotFound:
                to_return = None
        return to_return

    # maybe remove
    async def get_or_fetch_guild_entity(self, snowflake: id, guild_id: int, obj: str) -> Union[discord.Member, discord.User, discord.TextChannel, discord.VoiceChannel]:
        guild = self.get_guild(guild_id)
        if not guild:
            guild = await self.fetch_guild(guild_id)
        object_dict_list = {
            'channel': (guild.get_channel, guild.fetch_channel),
            'user': (guild.get_member, guild.fetch_member), 
        }
        action_to_take = object_dict_list.get(obj)
        to_return = action_to_take[0](snowflake)
        if not to_return:
            try:
                to_return = await action_to_take[1](snowflake)
            except discord.NotFound:
                to_return = None
        return to_return

    async def start(self, *args, **kwargs):
        async with aiohttp.ClientSession() as self.session:
            async with aiosqlite.connect('./databases/level.db') as self.level_conn:
                async with aiosqlite.connect('./databases/count.db') as self.count_conn:
                        async with aiosqlite.connect('./databases/config.db') as self.config_conn:
                            return await super().start(*args, **kwargs)

    def load_cogs(self):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and filename not in self.COG_DISABLED:
                self.load_extension(f'cogs.{filename[:-3]}')

    def check_for_outdated_logs(self):
        all_logs = os.listdir('./logs')
        if len(all_logs) > 30:
            to_delete = all_logs[20:]
            for log in to_delete:
                deletion = "./logs/{}".format(log)
                os.remove(deletion)
            print("Removed the following logs: ")
            print("\n".join(to_delete))

    def create_new_log(self):
        filename = './logs/{}.log'.format(self.formatted)
        handler = logging.FileHandler(filename=filename, encoding='utf-8', mode='w')
        formatter = logging.Formatter('| %(asctime)s: (%(levelname)s) %(name)s: %(message)s', '%H:%M:%S | %d %B %Y')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    async def check_ratelimit(self, message: discord.Message):
        current = datetime.datetime.utcnow()
        guild = message.guild
        if guild.id in self.cache:
            guild_ratelimit = self.cache[guild.id].rate_limit
            if message.author.id in guild_ratelimit:
                ratelimit, period = guild_ratelimit[message.author.id]
                time_difference = current - period
                if time_difference.total_seconds() < 300:
                    if ratelimit == config.RATELIMIT:
                        await helper.timeout_user(bot, user_id=message.author.id, guild_id=guild.id, until=10)
                        del guild_ratelimit[message.author.id]
                    else:
                        guild_ratelimit[message.author.id] = (ratelimit+1, period)
            else:
                guild_ratelimit[message.author.id] = (1, current)
        else:
            self.cache[message.guild.id] = helper.Cache({message.author.id: (1, current)})
        
bot = CountBot(command_prefix="$", intents=intents)

@bot.listen()
async def on_message(message: discord.Message):
    await bot.wait_until_ready()
    if message.author.bot or not message.guild:
        return
    if message.guild.id in bot.cache:
        cached_object = bot.cache[message.guild.id].count # {}
    else: # this
        cached_object = await send_cache_request(message.guild.id) # {} | {...}
    if not cached_object:
        return
    if message.channel.id == cached_object.get('channel_id'): # None | int
        content = message.content
        if content.isdigit():
            modified = cached_object['count'] + 1
            if message.author.id == cached_object.get('author_id') or int(content) != modified:
                await bot.check_ratelimit(message)
                return await message.delete()
            await record_and_cache_info(message)
        else:
            await message.delete()

@commands.is_owner()
@bot.command(name="clear")
async def _console(ctx):
    clear_console()

@bot.check
async def ready_check(ctx):
    await ctx.bot.wait_until_ready()
    return True

@bot.command()
async def uptime(ctx: commands.Context):
    time_delta = datetime.datetime.utcnow() - bot.uptime
    time_readable = humanize.precisedelta(time_delta, format="%0.1f")
    await ctx.send(f"The bot has been online for: {time_readable}")

async def record_and_cache_info(message):
    async with bot.count_conn.cursor() as cursor:
        await cursor.execute("UPDATE guilds SET (author_id) = ?, (count) = ?, (message_id) = ? WHERE guild_id = ?", 
                            (message.author.id, int(message.content), message.id, message.guild.id,)
                        )
    await bot.count_conn.commit()
    cached_object = bot.cache[message.guild.id]
    cached_object.count['count'] = int(message.content)
    cached_object.count['author_id'] = message.author.id


async def send_cache_request(guild_id):
    async with bot.count_conn.cursor() as cursor:
        record_cursor = await cursor.execute("SELECT count, channel_id, author_id FROM guilds WHERE guild_id = ?", (guild_id,))
        record = await record_cursor.fetchone()
    if guild_id in bot.cache:
        cached = bot.cache[guild_id].count
    else:
        bot.cache[guild_id] = helper.Cache()
        cached = bot.cache[guild_id].count
    if record:
        cached['count'] = record[0]
        cached['channel_id'] = record[1]
        cached['guild_id'] = record[2]
        bot.cache[guild_id].count = cached
    else:
        cached = None
        bot.cache[guild_id].count = cached
    return cached

async def create_table(cursor):
    await cursor.execute(
        '''CREATE TABLE guilds(
        guild_id INTEGER UNIQUE, 
        count INTEGER DEFAULT 0,
        author_id INTEGER DEFAULT 0,
        message_id INTEGER DEFAULT 0,
        channel_id INTEGER DEFAULT 0);'''
        )

async def startup_caching_task():
    async with aiosqlite.connect('./databases/count.db') as conn:
        async with conn.cursor() as cursor:
            try:
                await cursor.execute('SELECT guild_id, count, author_id, channel_id FROM guilds')
            except aiosqlite.OperationalError:
                await create_table(cursor)
                await cursor.execute('SELECT * FROM guilds')
            async for record in cursor:
                guild_id = record[0]
                count = record[1]
                author_id = record[2]
                channel_id = record[3]
                bot.cache[guild_id] = helper.Cache({'count': count, 'author_id': author_id, 'channel_id': channel_id})
        await conn.commit()

async def fill_suspicious_link():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://raw.githubusercontent.com/nikolaischunk/discord-phishing-links/main/domain-list.json") as response:
            text = json.loads(await response.text())
            bot.cache_suspicious_links = text['domains']
            
def create_multiple_tasks(loop):
    bot.load_cogs()
    bot.create_new_log()
    bot.check_for_outdated_logs()
    loop.create_task(startup_caching_task())
    loop.run_until_complete(fill_suspicious_link())

try:
    uvloop.install()
    create_multiple_tasks(bot.loop)
    TOKEN = config.TOKEN
    bot.run(TOKEN)
except (OSError, ConnectionError, discord.LoginFailure, KeyboardInterrupt) as e:
    print(e)
    print("disconnected!")
