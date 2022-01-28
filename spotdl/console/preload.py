import json
import concurrent.futures

from typing import List

from spotdl.download.downloader import Downloader
from spotdl.utils.query import parse_query


def preload(
    query: List[str],
    downloader: Downloader,
    save_path: str,
) -> None:
    """
    Search
    """

    # Parse the query
    songs = parse_query(query, downloader.threads)

    save_data = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=downloader.threads
    ) as executor:
        future_to_song = {
            executor.submit(downloader.audio_provider.search, song): song
            for song in songs
        }
        for future in concurrent.futures.as_completed(future_to_song):
            song = future_to_song[future]
            try:
                data = future.result()
                if data is None:
                    print(f"Didn't found download url for {song.display_name}")
                    continue

                print(f"Found url for {song.display_name}: {data}")
                save_data.append({**song.json, "download_url": data})
            except Exception as exc:  # pylint: disable=W0703
                print(f"{song} generated an exception: {exc}")

    # Save the songs to a file
    with open(save_path, "w", encoding="utf-8") as save_file:
        json.dump(save_data, save_file, indent=4, ensure_ascii=False)
