from pathlib import Path
from spotdl.types import Song
from typing import Any, Callable, Dict, List, Optional, Tuple

import asyncio
import sys
import concurrent.futures


class AudioProvider:
    def __init__(
        self,
        output_directory: str,
        threads: int = 1,
        output_format: str = "mp3",
        browsers: List[Tuple] = None,
    ) -> None:
        """
        Base class for audio providers.
        """

        if sys.platform == "win32":
            # ProactorEventLoop is required on Windows to run subprocess asynchronously
            # it is default since Python 3.8 but has to be changed for previous versions
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)

        self.loop = asyncio.get_event_loop()
        # semaphore is required to limit concurrent asyncio executions
        self.semaphore = asyncio.Semaphore(threads)

        # thread pool executor is used to run blocking (CPU-bound) code from a thread
        self.thread_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=threads
        )

        self.output_format = output_format
        self.output_directory = Path(output_directory)
        self.browsers = browsers

    async def download_single_song(self, song: Song) -> Tuple[Optional[Path], str]:
        """
        Download a song.
        """

        if song.download_url is None:
            url = self.search(song)
            if url is None:
                raise LookupError(
                    f"No results found for song: {song.name} - {song.artist}"
                )
        else:
            url = song.download_url

        return await self.perform_download(url), url

    async def perform_download(self, url: str) -> Optional[Path]:
        """
        The following function calls blocking code, which would block whole event loop.
        Therefore it has to be called in a separate thread via ThreadPoolExecutor. This
        is not a problem, since GIL is released for the I/O operations, so it shouldn't
        hurt performance.
        """

        return await self.loop.run_in_executor(
            self.thread_executor, self.perform_audio_download, url
        )

    def search(self, song: Song) -> Optional[str]:
        """
        Search for a song and return best match.
        """

        raise NotImplementedError

    def get_results(self, search_term: str) -> Optional[List[Any]]:
        """
        Get results from audio provider.
        """

        raise NotImplementedError

    def order_results(
        self,
        results: List[Any],
        song_name: str,
        song_artists: List[str],
        song_album_name: str,
        song_duration: int,
    ) -> Dict[str, Any]:
        """
        Order results.
        """

        raise NotImplementedError

    def perform_audio_download(self, url: str) -> Optional[Path]:
        """
        Perform audio download.
        """

        raise NotImplementedError

    def add_progress_hook(self, hook: Callable) -> None:
        """
        Add a hook to be called when the download progress changes.
        """

        raise NotImplementedError
