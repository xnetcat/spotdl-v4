from spotdl.providers.lyrics.base import LyricsProvider
from typing import List, Optional
from bs4 import BeautifulSoup

import requests


class Genius(LyricsProvider):
    def get_lyrics(self, name: str, artists: List[str]) -> Optional[str]:
        """
        Try to get lyrics from genius
        """

        headers = {
            "Authorization": "Bearer alXXDbPZtK1m2RrZ8I4k2Hn8Ahsd0Gh_o076HYvcdlBvmc0ULL1H8Z8xRlew5qaG",
        }

        headers.update(self.headers)

        artist_str = ", ".join(
            artist for artist in artists if artist.lower() not in name.lower()
        )

        search_response = requests.get(
            "https://api.genius.com/search",
            params={"q": f"{name} {artist_str}"},
            headers=headers,
        )
        if not search_response.ok:
            return None

        try:
            song_id = search_response.json()["response"]["hits"][0]["result"]["id"]
        except (IndexError, KeyError):
            return None

        song_response = requests.get(
            f"https://api.genius.com/songs/{song_id}", headers=headers
        )
        if not song_response.ok:
            return None

        song_url = song_response.json()["response"]["song"]["url"]
        genius_page_response = requests.get(song_url, headers=headers)
        if not genius_page_response.ok:
            return None

        soup = BeautifulSoup(
            genius_page_response.text.replace("<br/>", "\n"), "html.parser"
        )
        lyrics_div = soup.select_one("div.lyrics")

        if lyrics_div is not None:
            return lyrics_div.get_text().strip()

        lyrics_containers = soup.select("div[class^=Lyrics__Container]")
        lyrics = "\n".join(con.get_text() for con in lyrics_containers)
        return lyrics.strip()
