from spotdl.utils.formatter import create_song_title
from spotdl.utils.providers import match_percentage
from spotdl.providers.audio.base import AudioProvider
from spotdl.types import Song
from typing import Any, Callable, List, Optional
from pytube import YouTube as PyTube, Search
from slugify.main import Slugify
from yt_dlp import YoutubeDL
from pathlib import Path

slugify = Slugify(to_lower=True)


class YTDLLogger(object):
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        raise Exception(msg)


class YouTube(AudioProvider):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize YouTube provider
        """

        self.name = "youtube"
        super().__init__(*args, **kwargs)

        if self.output_format == "m4a":
            ytdl_format = "bestaudio[ext=m4a]/bestaudio/best"
        elif self.output_format == "opus":
            ytdl_format = "bestaudio[ext=webm]/bestaudio/best"
        else:
            ytdl_format = "bestaudio"

        self.audio_handler = YoutubeDL(
            {
                "format": ytdl_format,
                "outtmpl": f"{str(self.output_directory)}/%(id)s.%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "logger": YTDLLogger(),
                "cookiesfrombrowser": self.browsers,
            }
        )

    def perform_audio_download(self, url: str) -> Optional[Path]:
        """
        Download a song from YouTube Music and save it to the output directory.
        """

        data = self.audio_handler.extract_info(url)

        if data:
            return Path(self.output_directory / f"{data['id']}.{data['ext']}")

        return None

    def search(self, song: Song) -> Optional[str]:
        # if isrc is not None then we try to find song with it
        if song.isrc:
            isrc_results = self.get_results(song.isrc)

            if isrc_results and len(isrc_results) == 1:
                isrc_result = isrc_results[0]

                if isrc_result and isrc_result.watch_url is not None:
                    return isrc_result.watch_url

        slug_song_title = create_song_title(song.name, song.artists)

        # Query YTM by songs only first, this way if we get correct result on the first try
        # we don't have to make another request to ytmusic api that could result in us
        # getting rate limited sooner
        results = self.get_results(slug_song_title)

        if results is None:
            return None

        # Order results
        ordered_results = self.order_results(
            results, song.name, song.artists, song.duration
        )

        # No matches found
        if len(ordered_results) == 0:
            return None

        result_items = list(ordered_results.items())

        # Sort results by highest score
        sorted_results = sorted(result_items, key=lambda x: x[1], reverse=True)

        # Return the first result
        return sorted_results[0][0]

    def get_results(self, search_term: str) -> Optional[List[PyTube]]:
        """
        Get results from YouTube
        """
        return Search(search_term).results

    def order_results(
        self,
        results: List[PyTube],
        song_name: str,
        song_artists: List[str],
        song_duration: int,
    ) -> dict:

        # Assign an overall avg match value to each result
        links_with_match_value = {}

        # Slugify song title
        slug_song_title = slugify(create_song_title(song_name, song_artists))
        slug_song_name = slugify(song_name)

        for result in results:
            # Skip results without id
            if result.video_id is None:
                continue

            # Slugify some variables
            slug_result_name = slugify(result.title)
            sentence_words = slug_song_name.replace("-", " ").split(" ")

            # Check for common words in result name
            common_word = any(
                word != "" and word in slug_result_name for word in sentence_words
            )

            # skip results that have no common words in their name
            if not common_word:
                continue

            # Find artist match
            artist_match_number = 0.0

            # Calculate artist match for each artist
            # in the song's artist list
            for artist in song_artists:
                artist_match_number += match_percentage(
                    slugify(artist), slug_result_name
                )

            # skip results with artist match lower than 70%
            artist_match = artist_match_number / len(song_artists)
            if artist_match < 70:
                continue

            # Calculate name match
            name_match = match_percentage(slug_result_name, slug_song_title)

            # Drop results with name match lower than 50%
            if name_match < 50:
                continue

            # Calculate time match
            time_match = (
                100 - (result.length - song_duration ** 2) / song_duration * 100
            )

            average_match = (artist_match + name_match + time_match) / 3

            # the results along with the avg Match
            links_with_match_value[result.watch_url] = average_match

        return links_with_match_value

    def add_progress_hook(self, hook: Callable) -> None:
        """
        Add a hook to be called when the download progress changes.
        """
        self.audio_handler._progress_hooks.append(hook)
