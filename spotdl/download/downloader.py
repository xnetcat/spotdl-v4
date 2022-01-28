import json
import datetime
import asyncio
import traceback

from typing import List, Optional, Tuple

from spotdl.types import Song
from spotdl.utils.ffmpeg import FFmpeg
from spotdl.utils.ffmpeg import FFmpegError
from spotdl.utils.metadata import embed_metadata
from spotdl.utils.formatter import create_file_name
from spotdl.providers.audio.base import AudioProvider
from spotdl.providers.lyrics import Genius, MusixMatch
from spotdl.providers.lyrics.base import LyricsProvider
from spotdl.providers.audio import YouTube, YouTubeMusic
from spotdl.download.progress_handlers.logger import Logger
from spotdl.download.progress_handlers.tui import Tui
from spotdl.utils.config import get_errors_path, get_temp_path
from spotdl.download.progress_handlers.base import ProgressHandler


AUDIO_PROVIDERS = {
    "youtube": YouTube,
    "youtube-music": YouTubeMusic,
}

LYRICS_PROVIDERS = {
    "genius": Genius,
    "musixmatch": MusixMatch,
}

PROGRESS_HANDLERS = {
    "logger": Logger,
    "tui": Tui,
    # "gui": GuiProgressHandler,
}


class DownloaderError(Exception):
    """
    Base class for all exceptions related to downloaders.
    """


class Downloader:
    def __init__(
        self,
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
        """
        Initialize the Downloader class.
        """
        audio_provider_class = AUDIO_PROVIDERS.get(audio_provider)
        if audio_provider_class is None:
            raise DownloaderError(f"Invalid audio provider: {audio_provider}")

        lyrics_provider_class = LYRICS_PROVIDERS.get(lyrics_provider)
        if lyrics_provider_class is None:
            raise DownloaderError(f"Invalid lyrics provider: {lyrics_provider}")

        self.temp_directory = get_temp_path()
        if self.temp_directory.exists() is False:
            self.temp_directory.mkdir()

        self.output = output
        self.output_format = output_format
        self.save_file = save_file
        self.m3u_file = m3u_file
        self.threads = threads
        self.browsers = browsers
        self.overwrite = overwrite
        self.progress_handler = progress_handler
        self.audio_provider: AudioProvider = audio_provider_class(
            output_directory=self.temp_directory,
            threads=threads,
            output_format=output_format,
            browsers=browsers,
        )
        self.lyrics_provider: LyricsProvider = lyrics_provider_class()
        self.ffmpeg = FFmpeg(
            ffmpeg=ffmpeg,
            output_format=output_format,
            variable_bitrate=variable_bitrate,
            constant_bitrate=constant_bitrate,
            ffmpeg_args=["-abr", "true", "-v", "debug"]
            if ffmpeg_args is None
            else ffmpeg_args,
        )

        if self.progress_handler:
            self.progress_handler.debug("Downloader initialized")

    def download_song(self, song: Song) -> None:
        """
        Download a single song.
        """

        if self.progress_handler:
            self.progress_handler.set_song_count(1)

        self._download_asynchronously([song])

    def download_multiple_songs(self, songs: List[Song]) -> None:
        """
        Download multiple songs to the temp directory.
        After that convert the songs to the output format with ffmpeg.
        And move it to the output directory following the output format.
        Embed metadata to the songs.
        """

        if self.progress_handler:
            self.progress_handler.set_song_count(len(songs))

        self._download_asynchronously(songs)

    def _download_asynchronously(self, songs: List[Song]):
        """
        Download multiple songs asynchronously.
        """

        tasks = [self._pool_download(song) for song in songs]
        # call all task asynchronously, and wait until all are finished
        self.audio_provider.loop.run_until_complete(asyncio.gather(*tasks))

    async def _pool_download(self, song: Song) -> None:
        """
        Download a song to the temp directory.
        After that convert the song to the output format with ffmpeg.
        And move it to the output directory following the output format.
        Embed metadata to the song.
        """

        # Run asynchronous task in a pool to make sure that all processes
        # don't run at once.
        # tasks that cannot acquire semaphore will wait here until it's free
        # only certain amount of tasks can acquire the semaphore at the same time
        async with self.audio_provider.semaphore:
            # Initalize the progress tracker
            display_progress_tracker = None
            if self.progress_handler:
                display_progress_tracker = self.progress_handler.get_new_tracker(song)
                self.audio_provider.add_progress_hook(
                    display_progress_tracker.progress_hook
                )
            try:
                try:
                    temp_file, url = await self.audio_provider.download_single_song(
                        song
                    )
                except Exception as exception:
                    raise DownloaderError(
                        f'Unable to get audio stream for "{song.display_name}: {song.url}"'
                    ) from exception

                if self.progress_handler:
                    self.progress_handler.log(
                        f'Downloaded "{song.display_name}": {url}'
                    )

                # Song failed to download or something went wrong
                if temp_file is None:
                    return None

                if display_progress_tracker:
                    display_progress_tracker.notify_download_complete()

                output_file = create_file_name(song, self.output, self.output_format)
                if output_file.exists() is False:
                    output_file.parent.mkdir(parents=True, exist_ok=True)

                # Don't convert m4a files
                # just move the file to the output directory
                if temp_file.suffix == ".m4a" and self.output_format == "m4a":
                    temp_file.rename(output_file)
                    success = True
                    error_message = None
                else:
                    success, error_message = await self.ffmpeg.convert(
                        input_file=temp_file,
                        output_file=output_file,
                    )
                    temp_file.unlink()

                if success is False and error_message:
                    # If the conversion failed and there is an error message
                    # create a file with the error message
                    # and save it in the errors directory
                    # raise an exception with file path
                    file_name = get_errors_path() / f"ffmpeg_{datetime.date.today()}"
                    with open(file_name, "w", encoding="utf-8") as error_path:
                        json.dump(
                            error_message, error_path, ensure_ascii=False, indent=4
                        )

                    raise FFmpegError(
                        f"Failed to convert {song.name}"
                        f", you can find error here: {str(file_name.absolute())}"
                    )

                if display_progress_tracker:
                    display_progress_tracker.notify_conversion_complete()

                lyrics = self.lyrics_provider.get_lyrics(song.name, song.artists)
                if not lyrics:
                    if self.progress_handler:
                        self.progress_handler.debug(
                            f"No lyrics found for {song.name} - {song.artist}"
                        )

                    lyrics = ""

                embed_metadata(output_file, song, self.output_format, lyrics)
                if display_progress_tracker:
                    display_progress_tracker.notify_complete()

                if self.m3u_file:
                    # Append file path to m3u file
                    with open(self.m3u_file, "a+", encoding="utf-8") as m3u_file:
                        m3u_file.write(f"{output_file}\n")

                return None
            except Exception as exception:
                if display_progress_tracker:
                    display_progress_tracker.notify_error(
                        traceback.format_exc(), exception
                    )
                else:
                    raise exception
