from dataclasses import dataclass
from typing import List
from spotdl.types.song import Song
from spotdl.utils.spotify import SpotifyClient


class SavedError(Exception):
    """
    Base class for all exceptions related to saved tracks.
    """


@dataclass(frozen=True)
class Saved:
    tracks: List[Song]

    @classmethod
    def load(cls):
        """
        Loads saved tracks from Spotify.
        Will throw an exception if users is not logged in.
        """

        urls = cls.get_urls()

        # Remove songs without id
        # and create Song objects
        tracks = [Song.from_url(url) for url in urls]

        return cls(tracks)

    @staticmethod
    def get_urls() -> List[str]:
        """
        Returns a list of urls of all saved tracks.
        """

        spotify_client = SpotifyClient()
        if spotify_client.user_auth is False:  # type: ignore
            raise SavedError("You must be logged in to use this function.")

        saved_tracks_response = spotify_client.current_user_saved_tracks()
        if saved_tracks_response is None:
            raise Exception("Couldn't get saved tracks")

        saved_tracks = saved_tracks_response["items"]

        # Fetch all saved tracks
        while saved_tracks_response and saved_tracks_response["next"]:
            response = spotify_client.next(saved_tracks_response)
            # response is wrong, break
            if response is None:
                break

            saved_tracks_response = response
            saved_tracks.extend(saved_tracks_response["items"])

        # Remove songs without id
        # and return urls
        return [
            "https://open.spotify.com/track/" + track["track"]["id"]
            for track in saved_tracks
            if track and track.get("track", {}).get("id")
        ]
