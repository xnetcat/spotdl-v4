from spotdl.utils.formatter import create_song_title, parse_duration
from spotdl.utils.providers import match_percentage
from spotdl.providers.audio.base import AudioProvider
from spotdl.types import Song
from typing import Any, Callable, Dict, List, Optional
from ytmusicapi import YTMusic
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


class YouTubeMusic(AudioProvider):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the YouTube Music API
        """

        self.name = "youtube-music"
        super().__init__(*args, **kwargs)
        self.client = YTMusic()

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
        """
        Search for a song on YouTube Music.
        Return the link to the song if found.
        Or return None if not found.
        """

        # search for song using isrc if it's available
        if song.isrc is not None:
            isrc_results = self.get_results(song.isrc, "songs")

            if len(isrc_results) == 1:
                isrc_result = isrc_results[0]

                name_match = isrc_result["name"].lower() == song.name.lower()

                delta = isrc_result["duration"] - song.duration
                non_match_value = (delta ** 2) / song.duration * 100

                time_match = 100 - non_match_value

                if (
                    isrc_result
                    and isrc_result.get("link")
                    and name_match
                    and time_match > 90
                ):
                    return isrc_result["link"]

        song_title = create_song_title(song.name, song.artists).lower()

        # Query YTM by songs only first, this way if we get correct result on the first try
        # we don't have to make another request
        song_results = self.get_results(song_title, "songs")

        # Order results
        songs = self.order_results(
            song_results, song.name, song.artists, song.album_name, song.duration
        )

        # song type results are always more accurate than video type, so if we get score of 80 or above
        # we are almost 100% sure that this is the correct link
        if len(songs) != 0:
            # get the result with highest score
            best_result = max(songs, key=lambda k: songs[k])

            if songs[best_result] >= 80:
                return best_result

        # We didn't find the correct song on the first try so now we get video type results
        # add them to song_results, and get the result with highest score
        video_results = self.get_results(song_title, filter="videos")

        # Order video results
        videos = self.order_results(
            video_results, song.name, song.artists, song.album_name, song.duration
        )

        # Merge songs and video results
        results = {**songs, **videos}

        # No matches found
        if not results:
            return None

        result_items = list(results.items())

        # Sort results by highest score
        sorted_results = sorted(result_items, key=lambda x: x[1], reverse=True)

        # Get the result with highest score
        # and return the link
        return sorted_results[0][0]

    def get_results(self, search_term: str, filter: str) -> List[Dict[str, Any]]:
        """
        Get results from YouTube Music API and simplify them
        """

        results = self.client.search(search_term, filter=filter)

        # Simplify results
        simplified_results = []
        for result in results:
            if result.get("videoId") is None:
                continue

            simplified_results.append(
                {
                    "name": result["title"],
                    "type": result["resultType"],
                    "link": f"https://youtube.com/watch?v={result['videoId']}",
                    "album": result.get("album", {}).get("name"),
                    "duration": parse_duration(result.get("duration")),
                    "artists": ", ".join(map(lambda a: a["name"], result["artists"])),
                }
            )

        return simplified_results

    def order_results(
        self,
        results: List[Dict[str, Any]],
        song_name: str,
        song_artists: List[str],
        song_album_name: str,
        song_duration: int,
    ) -> Dict[str, Any]:

        # Slugify song title
        slug_song_title = slugify(create_song_title(song_name, song_artists))
        slug_song_name = slugify(song_name)
        slug_album_name = slugify(song_album_name)

        # Assign an overall avg match value to each result
        links_with_match_value = {}
        for result in results:
            # Slugify result title
            slug_result_name = slugify(result["name"])

            # check for common words in result name
            sentence_words = slug_song_name.replace("-", " ").split(" ")
            common_word = any(
                word != "" and word in slug_result_name for word in sentence_words
            )

            # skip results that have no common words in their name
            if not common_word:
                continue

            # Find artist match
            artist_match_number = 0.0
            if result["type"] == "song":
                for artist in song_artists:
                    artist_match_number += match_percentage(
                        slugify(artist), slugify(result["artists"])
                    )
            else:
                for artist in song_artists:
                    artist_match_number += match_percentage(
                        slugify(artist), slugify(result["name"])
                    )

                # If we didn't find any artist match,
                # we fallback to channel name match
                if artist_match_number == 0:
                    for artist in song_artists:
                        artist_match_number += match_percentage(
                            slugify(artist),
                            slugify(result["artists"]),
                        )

            # skip results with artist match lower than 70%
            artist_match = artist_match_number / len(song_artists)
            if artist_match < 70:
                continue

            # Calculate name match
            # for different result types
            if result["type"] == "song":
                name_match = match_percentage(slugify(result["name"]), slug_song_name)
            else:
                name_match = match_percentage(slugify(result["name"]), slug_song_title)

            # Drop results with name match lower than 50%
            if name_match < 50:
                continue

            # Find album match
            album_match = 0.0
            album = None

            # Calculate album match only for songs
            if result["type"] == "song":
                album = result.get("album")
                if album:
                    album_match = match_percentage(slugify(album), slug_album_name)

            # Calculate time match
            delta = result["duration"] - song_duration
            non_match_value = (delta ** 2) / song_duration * 100

            time_match = 100 - non_match_value

            if result["type"] == "song":
                if album is None:
                    # Don't use album match
                    # If we didn't find album for the result,
                    average_match = (artist_match + name_match + time_match) / 3
                elif (
                    match_percentage(album.lower(), result["name"].lower()) > 95
                    and album.lower() != song_album_name.lower()
                ):
                    # If the album name is similar to the result song name,
                    # But the album name is different from the song album name
                    # We don't use album match
                    average_match = (artist_match + name_match + time_match) / 3
                else:
                    average_match = (
                        artist_match + album_match + name_match + time_match
                    ) / 4
            else:
                # Don't use album match for videos
                average_match = (artist_match + name_match + time_match) / 3

            # the results along with the avg Match
            links_with_match_value[result["link"]] = average_match

        return links_with_match_value

    def add_progress_hook(self, hook: Callable) -> None:
        """
        Add a hook to be called when the download progress changes.
        """
        self.audio_handler._progress_hooks.append(hook)
