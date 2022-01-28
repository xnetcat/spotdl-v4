from spotdl.providers.lyrics.base import LyricsProvider
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import quote

import requests


class MusixMatch(LyricsProvider):
    def get_lyrics(
        self, name: str, artists: List[str], track_search: bool = False
    ) -> Optional[str]:
        """
        Try to get lyrics from musixmatch
        """

        artists_str = ", ".join(
            artist for artist in artists if artist.lower() not in name.lower()
        )

        # quote the query so that it's safe to use in a url
        # e.g "Au/Ra" -> "Au%2FRa"
        query = quote(f"{name} - {artists_str}", safe="")

        # search the `tracks page` if track_search is True
        if track_search:
            query += "/tracks"

        search_url = f"https://www.musixmatch.com/search/{query}"
        search_resp = requests.get(search_url, headers=self.headers)
        if not search_resp.ok:
            return None

        search_soup = BeautifulSoup(search_resp.text, "html.parser")
        song_url_tag = search_soup.select_one("a[href^='/lyrics/']")

        # song_url_tag being None means no results were found on the
        # All Results page, therefore, we use `track_search` to
        # search the tracks page.
        if song_url_tag is None:
            # track_serach being True means we are already searching the tracks page.
            if track_search:
                return None

            lyrics = self.get_lyrics(name, artists, track_search=True)
            return lyrics

        song_url = "https://www.musixmatch.com" + str(song_url_tag.get("href", ""))
        lyrics_resp = requests.get(song_url, headers=self.headers)
        if not lyrics_resp.ok:
            return None

        lyrics_soup = BeautifulSoup(lyrics_resp.text, "html.parser")
        lyrics_paragraphs = lyrics_soup.select("p.mxm-lyrics__content")
        lyrics = "\n".join(i.get_text() for i in lyrics_paragraphs)

        return lyrics
