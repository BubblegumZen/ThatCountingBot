from curses import start_color
import httpx
import asyncio
import discord
import datetime
import aiosqlite
import functools
from io import BytesIO
from typing import Tuple
from dataclasses import dataclass, field
from PIL import Image, ImageFont, ImageDraw

async def timeout_user(bot, *, user_id: int, guild_id: int, until):
    headers = {"Authorization": f"Bot {bot.http.token}"}
    url = f"https://discord.com/api/v9/guilds/{guild_id}/members/{user_id}"
    timeout = (datetime.datetime.utcnow() + datetime.timedelta(minutes=until)).isoformat()
    json = {'communication_disabled_until': timeout}
    async with bot.session.patch(url, json=json, headers=headers) as session:
        if session.status in range(200, 299):
           return True
        return False

def executor(loop=None, execute=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            partial = functools.partial(func, *args, **kwargs)
            under_loop = loop or asyncio.get_event_loop()
            return under_loop.run_in_executor(execute, partial)
        return wrapper
    return decorator


class RankCard:
    __slots__ = ('_session', '_member', 'font', 'font2', 'font3', 'font4')

    def __init__(self, session: httpx.AsyncClient, member: discord.Member) -> None:
        self._session: httpx.AsyncClient = session
        self._member: discord.Member = member
        self.font: ImageFont.FreeTypeFont = ImageFont.truetype("./Assets/Fonts/unicode-bold.ttf", 28)
        self.font2: ImageFont.FreeTypeFont = ImageFont.truetype("./Assets/Fonts/unicode-bold.ttf", 24)
        self.font3: ImageFont.FreeTypeFont = ImageFont.truetype("./Assets/Fonts/unicode-bold.ttf", 48)
        self.font4: ImageFont.FreeTypeFont = ImageFont.truetype("./Assets/Fonts/unicode-bold.ttf", 28)

    def calc_level(self, level):
        next_milestone = round(level*100 + ((level-1)*100)**0.5)
        return next_milestone

    def calculate_pixels(self, current_exp, next_milestone):
        start_pixel = 240
        to_cover = 600
        percentage = int((current_exp/next_milestone)*100)
        print(percentage)
        pixels = round((percentage/100)*to_cover)
        print(pixels)
        return start_pixel + pixels

    @executor()
    def get_original_bg(self) -> Image.Image:
        back = Image.new("RGBA", (934, 282))
        draw = ImageDraw.Draw(back)
        draw.rounded_rectangle(((0,0),(934, 282)),5,fill=(56,52,52))
        return back

    @executor()
    def get_translucent_inner_bg(self, *args) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
        exp, level = args[1], args[2]
        next_milestone = self.calc_level(level)
        to_draw = self.calculate_pixels(exp, next_milestone)
        new = Image.new("RGBA", (870, 230))
        draw = ImageDraw.Draw(new)
        draw.rounded_rectangle(((0,0),(870, 230)),5,fill="black", outline="black")
        new.putalpha(100)
        draw.rounded_rectangle(((240, 160),(840, 200)),50,fill="white") # empty bar
        draw.rounded_rectangle(((240, 160),(to_draw, 200)),50,fill="blue", outline="black") # bar fill
        return new, draw
    
    @executor()
    def add_text_to_translucent_bg(self, back: Image, new: Image.Image, draw: ImageDraw.ImageDraw, *args) -> Image.Image:
        rank, exp, level = args
        next_milestone = self.calc_level(level)
        to_draw = self.calculate_pixels(exp, next_milestone)
        draw.text((250, 120), str(self._member), (255,255,255), font=self.font)
        draw.text((560, 30), "RANK", (255,255,255), font=self.font2)
        draw.text((635, 5), f"#{rank}", (255,255,255), font=self.font3)
        draw.text((725, 30), "LEVEL", (255,255,255), font=self.font2)
        draw.text((805, 5), f"{level}", (255,255,255), font=self.font3)
        draw.text((715, 120), f"{exp}/{next_milestone}", (255,255,255), font=self.font4)
        Image.Image.paste(back, new, (30, 25))
        return back

    @executor()
    def add_rounded_avatar_to_picture(self, back: Image.Image, avatar: BytesIO) -> Image.Image:
        image = Image.open(avatar).resize((180, 180))
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse(((0, 0), (image.height, image.width)), fill=255)
        draw.ellipse(((225, 225), (325, 210)), fill=255)
        back.paste(image, (60, 50), mask)
        return back

    @executor()
    def push_in_buffer(self, image: Image.Image) -> BytesIO:
        buffer = BytesIO()
        image.save(buffer, "PNG")
        buffer.seek(0)
        return buffer
    
    async def get_avatar(self) -> BytesIO:
        url = self._member.avatar.url
        session = await self._session.get(url)
        avatar = BytesIO(await session.read())
        return avatar

    async def get_info(self):
        guild_id = self._member.guild.id
        member_id = self._member.id
        async with aiosqlite.connect("./databases/level.db") as conn:
            async with conn.cursor() as cursor:
                record_cursor = await cursor.execute("""SELECT ROW_NUMBER () OVER ( 
                                                        ORDER BY total_exp DESC, member_id DESC) RowNum,
                                                        exp, level FROM {} WHERE member_id = ?
                                                     """.format(f'x{guild_id}'), (member_id,))
                records = await record_cursor.fetchone()
        return records

    async def generate_rank_card(self) -> discord.File:
        info = await self.get_info()
        if info is None:
            return False
        print(info)
        avatar: BytesIO = await self.get_avatar()
        background_card: Image = await self.get_original_bg()
        translucent_inner_bg, translucent_inner_bg_draw = await self.get_translucent_inner_bg(*info) # Tuple[Image.Image, ImageDraw.ImageDraw]
        updated_background = await self.add_text_to_translucent_bg(background_card, 
                                                                   translucent_inner_bg, 
                                                                   translucent_inner_bg_draw, 
                                                                   *info)
        final_card = await self.add_rounded_avatar_to_picture(updated_background, avatar)
        buffer = await self.push_in_buffer(final_card)
        final_file = discord.File(buffer, filename="rank.png")
        return final_file


@dataclass(slots=True)
class Cache:
    count: dict = field(default_factory=dict) # {'author_id': int, 'channel_id': int}
    prefix: str = "$"
    rate_limit: dict = field(default_factory=dict) # {'author_id': (int, datetime.datetime)}
