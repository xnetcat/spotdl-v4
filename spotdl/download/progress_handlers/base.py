from typing import List

from spotdl.types import Song


# https://github.com/python/cpython/blob/3.10/Lib/logging/__init__.py
CRITICAL = 50
FATAL = CRITICAL
ERROR = 40
WARNING = 30
WARN = WARNING
INFO = 20
DEBUG = 10
NOTSET = 0

LEVEL_TO_NAME = {
    CRITICAL: "CRITICAL",
    ERROR: "ERROR",
    WARNING: "WARNING",
    INFO: "INFO",
    DEBUG: "DEBUG",
    NOTSET: "NOTSET",
}

NAME_TO_LEVEL = {
    "CRITICAL": CRITICAL,
    "FATAL": FATAL,
    "ERROR": ERROR,
    "WARN": WARNING,
    "WARNING": WARNING,
    "INFO": INFO,
    "DEBUG": DEBUG,
    "NOTSET": NOTSET,
}


class ProgressHandlerError(Exception):
    """
    Base class for all exceptions raised by ProgressHandler subclasses.
    """


class ProgressHandler:
    def __init__(self, log_level: int = INFO) -> None:
        """
        Initializes the progress handler.
        """

        self.songs: List[Song] = []
        self.song_count: int = 0
        self.overall_progress = 0
        self.overall_completed_tasks = 0

        if log_level not in LEVEL_TO_NAME:
            raise ProgressHandlerError(f"Invalid log level: {log_level}")

        self.log_level = log_level

    def set_song_count(self, count: int) -> None:
        """
        Sets the number of songs to be downloaded.
        """

        self.song_count = count
        self.overall_total = 100 * count

    def add_song(self, song: Song) -> None:
        """
        Adds a song to the list of songs.
        """

        self.songs.append(song)
        self.set_song_count(len(self.songs))

    def set_songs(self, songs: List[Song]) -> None:
        """
        Sets the list of songs to be downloaded.
        """

        self.songs = songs
        self.set_song_count(len(songs))

    def debug(self, message: str) -> None:
        """
        Logs a debug message.
        """

        raise NotImplementedError

    def log(self, message: str) -> None:
        """
        Logs a message.
        """

        raise NotImplementedError

    def warn(self, message: str) -> None:
        """
        Logs a warning message.
        """

        raise NotImplementedError

    def error(self, message: str) -> None:
        """
        Logs an error message.
        """

        if self.log_level < ERROR:
            pass

    def update_overall(self) -> None:
        """
        Updates the overall progress.
        """

        raise NotImplementedError

    def get_new_tracker(self, song: Song) -> "SongTracker":
        """
        Gets a new tracker.
        """

        return SongTracker(self, song)

    def close(self) -> None:
        """
        Closes the progress handler.
        """

        raise NotImplementedError


class SongTracker:
    def __init__(self, parent, song: Song) -> None:
        """
        Initializes the song tracker.
        """

        self.parent = parent
        self.song = song

        self.progress: int = 0
        self.old_progress: int = 0
        self.download_id: int = 0
        self.status = ""

    def update(self, message: str) -> None:
        """
        Updates the progress.
        """

        self.status = message

        # The change in progress since last update
        delta = self.progress - self.old_progress

        # If task is complete
        if self.progress == 100 or message == "Error":
            self.parent.overall_completed_tasks += 1

        # Update the overall progress bar
        self.parent.overall_progress += delta
        self.old_progress = self.progress

        self.parent.log(f"{self.song.name} - {self.song.artist}: {message}")
        self.parent.update_overall()

    def notify_error(self, message: str, traceback: Exception) -> None:
        """
        Logs an error message.
        """

        self.update(message="Error")

        self.parent.debug(message)
        self.parent.error(str(traceback))

    def notify_download_complete(self, status="Converting") -> None:
        """
        Notifies the progress handler that the song has been downloaded.
        """

        self.progress = 90
        self.update(status)

    def notify_conversion_complete(self, status="Tagging") -> None:
        """
        Notifies the progress handler that the song has been converted.
        """

        self.progress = 95
        self.update(status)

    def notify_complete(self, status="Done") -> None:
        """
        Notifies the progress handler that the song has been downloaded and converted.
        """

        self.progress = 100
        self.update(status)

    def progress_hook(self, *args, **kwargs) -> None:
        """
        Updates the progress.
        """

        # YT-dlp progress hook
        if type(args) == tuple and len(args) == 1:
            data = args[0]
            status = data.get("status")
            file_bytes = data.get("total_bytes")
            downloaded_bytes = data.get("downloaded_bytes")
            if None not in [status, file_bytes, downloaded_bytes]:
                if status == "downloading":
                    if file_bytes and downloaded_bytes:
                        self.progress = downloaded_bytes / file_bytes * 90

        self.update("Downloading")
