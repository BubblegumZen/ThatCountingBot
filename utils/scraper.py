from __future__ import annotations
import json
import re
import time
import random
import pprint
import aiohttp
import asyncio
from typing import Dict, Optional


class Anime:
    def __init__(self, *,
                 name: str,
                 cover: str,
                 age_rating: str,
                 description: str,
                 episodes: Optional[int],
                 rank: int,
                 show_type: str,
                 rating: str,
                 titles: Dict[str, str]) -> None:
        self.name = name
        self.cover = cover
        self.age_rating = age_rating
        self.description = description
        self.episodes = episodes
        self.rank = rank
        self.rating = rating
        self.type = show_type
        self.titles = titles

    @classmethod
    def from_dict(cls, json: dict) -> Anime:
        attrs = json['attributes']
        name = attrs['canonicalTitle']
        avg_rating = attrs['averageRating']
        age_rating = attrs['ageRating']
        description = attrs['description']
        episodes = attrs['episodeCount']
        poster_image = attrs['posterImage']['large']
        rank = attrs['popularityRank']
        show_type = attrs['showType']
        titles = attrs['titles']
        return cls(
                    name=name,
                    cover=poster_image,
                    age_rating=age_rating,
                    rating=avg_rating,
                    episodes=episodes,
                    description=description,
                    rank=rank,
                    show_type=show_type,
                    titles=titles
                  )



class Scraper:
    BASE = "https://myanimelist.net"
    FORMATTABLE_REGEX = "({}\?page=[0-9]+)"
    def __init__(self, *, session: Optional[aiohttp.ClientSession] = None, amount: int = 1) -> None:
        self._anime_regex = '(\/anime\/[0-9]+\/[A-Za-z_\-]+)'
        self.amount = amount
        self._session: Optional[aiohttp.ClientSession] = session
        self.full_list = ['/anime/genre/1/Action', '/anime/genre/2/Adventure', '/anime/genre/3/Cars', '/anime/genre/4/Comedy', '/anime/genre/5/Avant', 
                          '/anime/genre/6/Demons', '/anime/genre/7/Mystery', '/anime/genre/8/Drama', '/anime/genre/9/Ecchi', '/anime/genre/10/Fantasy', 
                          '/anime/genre/11/Game', '/anime/genre/13/Historical', '/anime/genre/14/Horror', '/anime/genre/15/Kids', 
                          '/anime/genre/17/Martial', '/anime/genre/18/Mecha', '/anime/genre/19/Music', '/anime/genre/20/Parody', '/anime/genre/21/Samurai', 
                          '/anime/genre/22/Romance', '/anime/genre/23/School', '/anime/genre/24/Sci', '/anime/genre/25/Shoujo', '/anime/genre/26/Girls', 
                          '/anime/genre/27/Shounen', '/anime/genre/28/Boys', '/anime/genre/29/Space', '/anime/genre/30/Sports', '/anime/genre/31/Super', 
                          '/anime/genre/32/Vampire', '/anime/genre/35/Harem', '/anime/genre/36/Slice', '/anime/genre/37/Supernatural', '/anime/genre/38/Military', 
                          '/anime/genre/39/Police', '/anime/genre/40/Psychological', '/anime/genre/41/Suspense', '/anime/genre/42/Seinen', '/anime/genre/43/Josei', 
                          '/anime/genre/46/Award', '/anime/genre/47/Gourmet', '/anime/genre/48/Work']

    @property
    def get_all_genres(self):
        return sorted([string.split('/')[-1] for string in self.full_list])

    @staticmethod
    def parse_anime_link(url: str):
        splited = url.split('/')
        anime_name = splited[-1]
        anime_id = splited[-2]
        correctives = [('__', ': '), ('_', ' '), ('TV', '(TV)')]
        for old, corrected in correctives:
            anime_name = anime_name.replace(old, corrected)
        return anime_name       

    async def require_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def get_text(self, url: str):
        await self.require_session()
        response = await self._session.get(url)
        text = await response.text()
        return text

    async def get_all_pages(self, text: str, genre: str):
        modified_genre = genre.replace('/', r'\/')
        request_link_regex = self.FORMATTABLE_REGEX.format(modified_genre)
        text_response = re.findall(request_link_regex, text)
        try:
            last_page = text_response[-1]
        except IndexError:
            return await self.connect()
        last_page_num = int(last_page.split('=')[-1])
        to_return = [self.BASE + genre + f"?page={num}" for num in range(1, last_page_num+1)]
        return to_return

    async def parse_information(self, text: str):
        all_animes = re.findall(self._anime_regex, text)
        return [x.split('"')[0] for x in all_animes]

    async def fetch_anime_information(self, name: str):
        await self.require_session()
        params = {'filter[text]=': name}
        url = 'https://kitsu.io/api/edge/anime'
        response = await self._session.get(url, params=params)
        json_response = await response.json()
        return json_response['data'][0]

    async def connect(self):
        genre = random.choice(self.full_list)
        response = await self.get_text(self.BASE + genre)
        pages = await self.get_all_pages(response, genre)
        page_to_pick = random.choice(pages)
        new_response = await self.get_text(page_to_pick) 
        parsed_information = await self.parse_information(new_response)
        animes_to_pick = random.sample(parsed_information, self.amount)
        final_result = [self.parse_anime_link(anime) for anime in animes_to_pick]
        anime_information = [await self.fetch_anime_information(result) for result in final_result]
        anime_class = [Anime.from_dict(anime) for anime in anime_information]
        return anime_class

    def __del__(self):
        asyncio.run(self._session.close())


if __name__ == "__main__":
    start = time.perf_counter()
    class_instance = Scraper()
    coroutine = class_instance.connect()
    asyncio.run(coroutine)
    end = time.perf_counter()
    print('Finished in:', round(end-start, 2), "seconds")
