from dataclasses import dataclass
from typing import Any, Dict, List
from spotdl.utils.spotify import SpotifyClient
from spotdl.types.song import Song


class AlbumError(Exception):
    """
    Base class for all exceptions related to albums.
    """


@dataclass(frozen=True)
class Album:
    name: str
    url: str
    tracks: List[Song]
    artist: Dict[str, Any]

    @classmethod
    def from_url(cls, url: str) -> "Album":
        """
        Parse an album from a Spotify URL.
        """

        spotify_client = SpotifyClient()

        album_metadata = spotify_client.album(url)
        if album_metadata is None:
            raise AlbumError(
                "Couldn't get metadata, check if you have passed correct album id"
            )

        urls = cls.get_urls(url)

        # Remove songs without id (country restricted/local tracks)
        # And create song object for each track
        songs: List[Song] = [Song.from_url(url) for url in urls]

        return cls(
            name=album_metadata["name"],
            url=url,
            tracks=songs,
            artist=album_metadata["artists"][0],
        )

    @property
    def length(self) -> int:
        """
        Get Album length (number of tracks).
        """

        return len(self.tracks)

    @staticmethod
    def get_urls(url: str) -> List[str]:
        """
        Get urls for all songs in album.
        """

        spotify_client = SpotifyClient()

        album_response = spotify_client.album_tracks(url)
        if album_response is None:
            raise AlbumError(
                "Couldn't get metadata, check if you have passed correct album id"
            )

        tracks = album_response["items"]

        # Get all tracks from album
        while album_response["next"]:
            album_response = spotify_client.next(album_response)

            # Failed to get response, break the loop
            if album_response is None:
                break

            tracks.extend(album_response["items"])

        if album_response is None:
            raise AlbumError(f"Failed to get album response: {url}")

        return [
            track["external_urls"]["spotify"]
            for track in tracks
            if track and track.get("id")
        ]
