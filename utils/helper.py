import re
import httpx
import base64
import string
import asyncio
import discord
import datetime
import aiosqlite
import functools
import urllib.parse
from io import BytesIO
from typing import Tuple
from colorthief import ColorThief
from dataclasses import dataclass, field
from PIL import Image, ImageFont, ImageDraw
from datetime import datetime as dt, timedelta

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


class Spotify:
    __slots__ = ('member', 'bot', 'embed', 'regex', 'headers', 'counter')
    
    def __init__(self, *, bot, member) -> None:
        """
        Class that represents a Spotify object, used for creating listening embeds

        Parameters:
        ----------------
        bot : commands.Bot
            represents the Bot object
        member : discord.Member
            represents the Member object whose spotify listening is to be handled
        """
        self.member = member
        self.bot = bot
        self.embed = discord.Embed(title=f"{member.display_name} is Listening to Spotify", color=self.bot.theme)
        self.regex = "(https\:\/\/open\.spotify\.com\/artist\/[a-zA-Z0-9]+)"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/75.0.3770.100 Safari/537.36'}
        self.counter = 0

    async def request_pass(self, *, track_id: str):
        """
        Requests for a list of artists from the spotify API

        Parameters:
        ----------------
            track_id : str
                Spotify track's id

        Returns
        ----------------
        list
            A list of artist details

        Raises
        ----------------
        Exception
            If Spotify API is down
        """
        try:
            headers = {"Authorization":
                           f'Basic {base64.urlsafe_b64encode(f"{self.bot.spotify_client_id}:{self.bot.spotify_client_secret}".encode()).decode()}',
                       "Content-Type":
                           "application/x-www-form-urlencoded", }
            params = {"grant_type": "client_credentials"}
            if not self.bot.spotify_session or dt.utcnow() > self.bot.spotify_session[1]:
                resp = await self.bot.session.post("https://accounts.spotify.com/api/token",
                                                   params=params, headers=headers)
                auth_js = await resp.json()
                timenow = dt.utcnow() + timedelta(seconds=auth_js['expires_in'])
                type_token = auth_js['token_type']
                token = auth_js['access_token']
                auth_token = f"{type_token} {token}"
                self.bot.spotify_session = (auth_token, timenow)
                print('Generated new Token')
            else:
                auth_token = self.bot.spotify_session[0]
                print('Using previous token')
        except Exception:
            raise Exception("Something went wrong!")
        else:
            try:
                resp = await self.bot.session.get(f"https://api.spotify.com/v1/tracks/{urllib.parse.quote(track_id)}",
                                                  params={
                                                      "market": "US",
                                                  },
                                                  headers={
                                                      "Authorization": auth_token},
                                                  )
                json = await resp.json()
                return json
            except Exception:
                if self.counter == 4:
                    raise Exception("Something went wrong!")
                else:
                    self.counter += 1
                    await self.request_pass(track_id=track_id)

    @staticmethod
    @executor()
    def pil_process(pic, name, artists, time, time_at, track) -> discord.File:
        """
        Makes an image with spotify album cover with Pillow
        
        Parameters:
        ----------------
        pic : BytesIO
            BytesIO object of the album cover
        name : str
            Name of the song
        artists : list
            Name(s) of the Artists
        time : int
            Total duration of song in seconds
        time_at : int
            Total duration into the song in seconds
        track : int
            Offset for covering the played bar portion

        Returns
        ----------------
        discord.File
            contains the spotify image
        """
        s = ColorThief(pic)
        color = s.get_palette(color_count=2)
        result = Image.new('RGBA', (575, 170))
        draw = ImageDraw.Draw(result)
        color_font = "white" if sum(color[0]) < 450 else "black"
        draw.rounded_rectangle(((0, 0), (575, 170)), 20, fill=color[0])
        s = Image.open(pic)
        s = s.resize((128, 128))
        result1 = Image.new('RGBA', (129, 128))
        Image.Image.paste(result, result1, (29, 23))
        Image.Image.paste(result, s, (27, 20))
        font = ImageFont.truetype("Assets/Fonts/spotify.ttf", 28)
        font2 = ImageFont.truetype("Assets/Fonts/spotify.ttf", 18)
        draw.text((170, 20), name, color_font, font=font)
        draw.text((170, 55), artists, color_font, font=font2)
        draw.text((500, 120), time, color_font, font=font2)
        draw.text((170, 120), time_at, color_font, font=font2)
        draw.rectangle(((230, 130), (490, 127)), fill="grey")  # play bar
        draw.rectangle(((230, 130), (230 + track, 127)), fill=color_font)
        draw.ellipse((230 + track - 5, 122, 230 + track + 5, 134), fill=color_font, outline=color_font)
        draw.ellipse((230 + track - 6, 122, 230 + track + 6, 134), fill=color_font, outline=color_font)
        output = BytesIO()
        result.save(output, "png")
        output.seek(0)
        return discord.File(fp=output, filename="spotify.png")

    async def get_from_local(self, bot, act: discord.Spotify) -> discord.File:
        """
        Makes an image with spotify album cover with Pillow
        
        Parameters:
        ----------------
        bot : commands.Bot
            represents our Bot object
        act : discord.Spotify
            activity object to get information from

        Returns
        ----------------
        discord.File
            contains the spotify image
        """
        s = tuple(f"{string.ascii_letters}{string.digits}{string.punctuation} ")
        artists = ', '.join(act.artists)
        artists = ''.join([x for x in artists if x in s])
        artists = artists[0:36] + "..." if len(artists) > 36 else artists
        time = act.duration.seconds
        time_at = (datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) - act.start).total_seconds()
        track = (time_at / time) * 260
        time = f"{time // 60:02d}:{time % 60:02d}"
        time_at = f"{int((time_at if time_at > 0 else 0) // 60):02d}:{int((time_at if time_at > 0 else 0) % 60):02d}"
        pog = act.album_cover_url
        name = ''.join([x for x in act.title if x in s])
        name = name[0:21] + "..." if len(name) > 21 else name
        rad = await bot.session.get(pog)
        pic = BytesIO(await rad.read())
        return await self.pil_process(pic, name, artists, time, time_at, track)

    @staticmethod
    async def fetch_from_api(bot, activity: discord.Spotify):
        """
        Request an image for spotify from Jeyy API
        
        Parameters:
        ----------------
        bot : commands.Bot
            represents our Bot object
        activity : discord.Spotify
            activity object to get information from

        Returns
        ----------------
        discord.File
            contains the spotify image
        """
        act = activity
        base_url = "https://api.jeyy.xyz/discord/spotify"
        params = {'title': act.album, 'cover_url': act.album_cover_url, 'artists': act.artists[0],
                  'duration_seconds': act.duration.seconds, 'start_timestamp': int(act.start.timestamp())}
        connection = await bot.session.get(base_url, params=params)
        buffer = BytesIO(await connection.read())
        return discord.File(fp=buffer, filename="spotify.png")

    async def send_backup_artist_request(self, activity: discord.Spotify):
        """
        Backup request if spotify API is down
        
        Parameters:
        ----------------
        activity : discord.Spotify
            activity object to get information from

        Returns
        ----------------
        str
            the names of the artists and their artist links respectively
        """
        artists = activity.artists
        url = activity.track_url
        result = await self.bot.session.get(url, headers=self.headers)
        text = await result.text()
        my_list = re.findall(self.regex, text)
        final = sorted(set(my_list), key=my_list.index)
        total = len(artists)
        final_total = final[0:total]
        final_string = ', '.join([f"[{artists[final_total.index(x)]}]({x})" for x in final_total])
        return final_string

    async def get_embed(self) -> Tuple[discord.Embed, discord.File]:
        """
        Creates the Embed object
        
        Returns
        ----------------
        Tuple[discord.Embed, discord.File]
            the embed object and the file with spotify image
        """
        activity = discord.utils.find(lambda activity: isinstance(activity, discord.Spotify), self.member.activities)
        if not activity:
            return False
        try:
            result = await self.request_pass(track_id=activity.track_id)
            final_string = ', '.join(
                [f"[{resp['name']}]({resp['external_urls']['spotify']})" for resp in result['artists']])
        except Exception:
            final_string = await self.send_backup_artist_request(activity)
        url = activity.track_url
        image = await self.get_from_local(self.bot, activity)
        self.embed.description = f"**Artists**: {final_string}\n**Album**: [{activity.album}]({url})"
        self.embed.set_image(url="attachment://spotify.png")
        return self.embed, image

@dataclass(slots=True)
class Cache:
    count: dict = field(default_factory=dict) # {'author_id': int, 'channel_id': int}
    prefix: str = "$" # str
    rate_limit: dict = field(default_factory=dict) # {'author_id': (int, datetime.datetime)}
