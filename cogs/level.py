import discord
import random
import aiosqlite
from discord.ext import commands
from utils.helper import RankCard



class Level(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cd_mapping = commands.CooldownMapping.from_cooldown(1, 15, commands.BucketType.member)

    def calc_level(self, level):
        next_milestone = round(level*100 + ((level-1)*100)**0.5)
        return next_milestone

    async def create_table(self, conn, cursor, message: discord.Message):
        await cursor.execute(f"""CREATE TABLE x{message.guild.id}(
                                 member_id INTEGER UNIQUE,
                                 exp INTEGER DEFAULT 0,
                                 total_exp INTEGER DEFAULT 0,
                                 level INTEGER DEFAULT 1
                             )""")
        await conn.commit()

    def check_level_up(self, level: int, current: int):
        next_milestone = self.calc_level(level)
        if current > next_milestone:
            return current - next_milestone
        else:
            return False

    async def register_in_db(self, conn, cursor, message, amount):
        await cursor.execute("INSERT INTO {}(member_id, exp, total_exp) VALUES(?,?,?)".format(f"x{message.guild.id}"), (message.author.id, amount, amount))
        await conn.commit()

    async def update_in_db(self, conn, cursor, message, amount, *args):
        current_exp = args[0] + amount
        level = args[2]
        handshake = self.check_level_up(level, current_exp)
        if handshake:
            current_exp = handshake
            await cursor.execute("UPDATE {} SET level = level + 1, total_exp = total_exp + ?, exp = ?".format(f"x{message.guild.id}"), (amount, current_exp))
        else:
            await cursor.execute("UPDATE {} SET total_exp = total_exp + ?, exp = ?".format(f"x{message.guild.id}"), (amount, current_exp))
        await conn.commit()

    async def register_or_update_db(self, message: discord.Message, amount: int):
        await self.check_for_presence(message)
        async with aiosqlite.connect('./databases/level.db') as conn:
            async with conn.cursor() as cursor:
                record_cursor = await cursor.execute("SELECT exp, total_exp, level FROM {} WHERE member_id = ?".format(f"x{message.guild.id}"), (message.author.id,))
                records = await record_cursor.fetchone()
                if not records:
                    await self.register_in_db(conn, cursor, message, amount)
                else:   
                    await self.update_in_db(conn, cursor, message, amount, *records)

    async def check_for_presence(self, message: discord.Message):
        async with aiosqlite.connect('./databases/level.db') as conn:
            async with conn.cursor() as cursor:
                try:
                    record_cursor = await cursor.execute("SELECT exp, total_exp FROM {} WHERE member_id = ?".format(f"x{message.guild.id}"), (message.author.id,))
                    records = await record_cursor.fetchone()
                except aiosqlite.OperationalError:
                    await self.create_table(conn, cursor, message)
                    record_cursor = await cursor.execute("SELECT exp, total_exp FROM {} WHERE member_id = ?".format(f"x{message.guild.id}"), (message.author.id,))
                    records = await record_cursor.fetchone()
        return records
        
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        context = await self.bot.get_context(message)
        if context.command:
            return
        bucket = self.cd_mapping.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            print("returning")
            return
        exp_to_grant = random.randint(1, 15)
        print(exp_to_grant)
        await self.register_or_update_db(message, exp_to_grant)

    @commands.command()
    async def rank(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        rank_card = RankCard(self.bot.session, member)
        card = await rank_card.generate_rank_card()
        await ctx.send(file=card)



def setup(bot):
    bot.add_cog(Level(bot))
        

        