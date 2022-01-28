import logging

from spotdl.download.progress_handlers.base import (
    ProgressHandler,
    SongTracker,
    DEBUG,
    INFO,
    WARNING,
    ERROR,
    CRITICAL,
)
from spotdl.types.song import Song


class Logger(ProgressHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        logging.basicConfig(
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
            level=self.log_level,
        )

        self.previous_overall = self.overall_completed_tasks

    def debug(self, message: str) -> None:
        logging.debug(message)

    def log(self, message: str) -> None:
        logging.info(message)

    def warn(self, message: str) -> None:
        logging.warning(message)

    def error(self, message: str) -> None:
        logging.error(message)

    def update_overall(self) -> None:
        if self.previous_overall != self.overall_completed_tasks:
            logging.info(f"{self.overall_completed_tasks}/{self.song_count} complete")
            self.previous_overall = self.overall_completed_tasks

    def get_new_tracker(self, song: Song):
        return SongTracker(self, song)

    def close(self) -> None:
        logging.shutdown()
