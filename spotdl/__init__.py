__version__ = "4.0.0"

import concurrent.futures

from pathlib import Path
from typing import List, Optional, Tuple

from spotdl.download.downloader import AUDIO_PROVIDERS, DownloaderError
from spotdl.download.progress_handlers.base import ProgressHandler
from spotdl.utils.spotify import SpotifyClient
from spotdl.console import console_entry_point
from spotdl.utils.query import parse_query
from spotdl.download import Downloader
from spotdl.types import Song


class Spotdl:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_auth: bool = False,
        audio_provider: str = "youtube-music",
        lyrics_provider: str = "musixmatch",
        ffmpeg: str = "ffmpeg",
        variable_bitrate: str = None,
        constant_bitrate: str = None,
        ffmpeg_args: Optional[List] = None,
        output_format: str = "mp3",
        threads: int = 4,
        output: str = ".",
        save_file: Optional[str] = None,
        m3u_file: Optional[str] = None,
        overwrite: str = "overwrite",
        browsers: Optional[Tuple] = None,
        progress_handler: Optional[ProgressHandler] = None,
    ):
        # Initialize spotify client
        SpotifyClient.init(
            client_id=client_id, client_secret=client_secret, user_auth=user_auth
        )

        # Initialize downloader
        self.downloader = Downloader(
            audio_provider,
            lyrics_provider,
            ffmpeg,
            variable_bitrate,
            constant_bitrate,
            ffmpeg_args,
            output_format,
            threads,
            output,
            save_file,
            m3u_file,
            overwrite,
            browsers,
            progress_handler,
        )

        self.audio_provider = audio_provider

    def get_download_urls(self, songs: List[Song]) -> List[Optional[str]]:
        """
        Search .
        """

        urls = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.downloader.threads
        ) as executor:
            future_to_song = {
                executor.submit(self.downloader.audio_provider.search, song): song
                for song in songs
            }
            for future in concurrent.futures.as_completed(future_to_song):
                song = future_to_song[future]
                try:
                    data = future.result()
                    urls.append(data)
                except Exception as exc:  # pylint: disable=W0703
                    print(f"{song} generated an exception: {exc}")

        return urls

    def parse_query(self, query: List[str]) -> List[Song]:
        """
        Parse a list of queries and return a list of Song objects.
        """

        return parse_query(query, self.downloader.threads)

    def download(self, song: Song) -> None:
        """
        Download and convert song to the output format.
        """

        self.downloader.download_song(song)

    async def download_no_convert(self, song: Song) -> Tuple[Optional[Path], str]:
        """
        Download song without converting it.
        """

        return await self.downloader.audio_provider.download_single_song(song)

    def download_list(self, songs: List[Song]) -> None:
        """
        Download and convert songs to the output format.
        """

        self.downloader.download_multiple_songs(songs)

    def change_output_directory(self, output_directory: Path) -> None:
        """
        Change the output directory.
        This is done by reinitializing the audio provider.
        """

        audio_provider_class = AUDIO_PROVIDERS.get(self.audio_provider)

        if audio_provider_class is None:
            raise DownloaderError(f"Invalid audio provider: {self.audio_provider}")

        self.downloader.audio_provider = audio_provider_class(
            output_directory=output_directory,
            threads=self.downloader.threads,
            output_format=self.downloader.output_format,
            browsers=self.downloader.browsers,
        )
