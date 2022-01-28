import traceback

from pathlib import Path
from typing import List

from spotdl.download.downloader import Downloader
from spotdl.utils.query import parse_query
from spotdl.utils.formatter import create_file_name


def download(
    query: List[str],
    downloader: Downloader,
) -> None:
    """
    Find matches on youtube, download the songs, and save them to the disk.
    """

    try:
        songs_list = parse_query(query, downloader.threads)

        songs = []
        for song in songs_list:
            song_path = create_file_name(
                song, downloader.output, downloader.output_format
            )

            if Path(song_path).exists():
                if downloader.overwrite == "overwrite":
                    songs.append(song)
            else:
                songs.append(song)

        downloader.download_multiple_songs(songs)
    except Exception as exception:
        if downloader.progress_handler:
            downloader.progress_handler.debug(traceback.format_exc())
            downloader.progress_handler.error(str(exception))
