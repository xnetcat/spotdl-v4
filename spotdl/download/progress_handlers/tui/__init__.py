from typing import Optional

from rich.text import Text
from rich.theme import Theme
from rich.progress import Task
from rich.console import Console
from rich.style import StyleType
from rich.highlighter import Highlighter
from rich.progress import BarColumn, TimeRemainingColumn, Progress, ProgressColumn
from rich.console import (
    JustifyMethod,
    detect_legacy_windows,
    OverflowMethod,
)

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

THEME = Theme(
    {
        "bar.back": "grey23",
        "bar.complete": "rgb(165,66,129)",
        "bar.finished": "rgb(114,156,31)",
        "bar.pulse": "rgb(165,66,129)",
        "general": "green",
        "nonimportant": "rgb(40,100,40)",
        "progress.data.speed": "red",
        "progress.description": "none",
        "progress.download": "green",
        "progress.filesize": "green",
        "progress.filesize.total": "green",
        "progress.percentage": "green",
        "progress.remaining": "rgb(40,100,40)",
    }
)


class SizedTextColumn(ProgressColumn):
    """A column containing text."""

    def __init__(
        self,
        text_format: str,
        style: StyleType = "none",
        justify: JustifyMethod = "left",
        markup: bool = True,
        highlighter: Highlighter = None,
        overflow: Optional[OverflowMethod] = None,
        width: int = 20,
    ) -> None:
        self.text_format = text_format
        self.justify: JustifyMethod = justify
        self.style = style
        self.markup = markup
        self.highlighter = highlighter
        self.overflow: Optional[OverflowMethod] = overflow
        self.width = width
        super().__init__()

    def render(self, task: "Task") -> Text:
        _text = self.text_format.format(task=task)
        if self.markup:
            text = Text.from_markup(_text, style=self.style, justify=self.justify)
        else:
            text = Text(_text, style=self.style, justify=self.justify)
        if self.highlighter:
            self.highlighter.highlight(text)

        text.truncate(max_width=self.width, overflow=self.overflow, pad=True)
        return text


class Tui(ProgressHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Change color system if "legacy" windows terminal to prevent wrong colors displaying
        self.is_legacy = detect_legacy_windows()

        # dumb_terminals automatically handled by rich. Color system is too but it is incorrect
        # for legacy windows ... so no color for y'all.
        self.console = Console(
            theme=THEME, color_system="truecolor" if not self.is_legacy else None
        )

        self.rich_progress_bar = Progress(
            SizedTextColumn(
                "[white]{task.description}",
                overflow="ellipsis",
                width=int(self.console.width / 3),
            ),
            SizedTextColumn("{task.fields[message]}", width=18, style="nonimportant"),
            BarColumn(bar_width=None, finished_style="green"),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeRemainingColumn(),
            console=self.console,
            # Normally when you exit the progress context manager (or call stop())
            # the last refreshed display remains in the terminal with the cursor on
            # the following line. You can also make the progress display disappear on
            # exit by setting transient=True on the Progress constructor
            transient=self.is_legacy,
        )

        self.quiet = self.log_level > 20
        self.overall_task_id = None

        # Basically a wrapper for rich's: with ... as ...
        self.rich_progress_bar.__enter__()

    def set_song_count(self, count: int) -> None:
        super().set_song_count(count)

        if self.song_count > 4:
            self.overall_task_id = self.rich_progress_bar.add_task(
                description="Total",
                process_id="0",
                message=(
                    f"{self.overall_completed_tasks}/{int(self.overall_total / 100)}"
                    "complete"
                ),
                total=self.overall_total,
                visible=(not self.quiet),
            )

    def debug(self, message: str) -> None:
        if self.log_level > DEBUG:
            return

        self.rich_progress_bar.console.print(f"[blue]{message}")

    def log(self, message: str) -> None:
        if self.log_level > INFO:
            return

        self.rich_progress_bar.console.print(f"[green]{message}")

    def warn(self, message: str) -> None:
        if self.log_level > WARNING:
            return

        self.rich_progress_bar.console.print(f"[yellow]{message}")

    def error(self, message: str) -> None:
        if self.log_level > ERROR:
            return

        self.rich_progress_bar.console.print(f"[red]{message}")

    def update_overall(self) -> None:
        # If the overall progress bar exists
        if self.overall_task_id is not None:
            self.rich_progress_bar.update(
                self.overall_task_id,
                message=f"{self.overall_completed_tasks}/{int(self.overall_total / 100)} complete",
                completed=self.overall_progress,
            )

    def get_new_tracker(self, song: Song):
        return TuiSongTracker(self, song)

    def close(self) -> None:
        self.rich_progress_bar.stop()


class TuiSongTracker(SongTracker):
    def __init__(self, parent, song: Song) -> None:
        super().__init__(parent, song)

        self.task_id = self.parent.rich_progress_bar.add_task(
            description=song.display_name,
            process_id=str(self.download_id),
            message="Download Started",
            total=100,
            completed=self.progress,
            start=False,
            visible=(not self.parent.quiet),
        )

    def update(self, message=""):
        """
        Called at every event.
        """

        self.status = message

        # The change in progress since last update
        delta = self.progress - self.old_progress

        # Update the progress bar
        # `start_task` called everytime to ensure progress is remove from indeterminate state
        self.parent.rich_progress_bar.start_task(self.task_id)
        self.parent.rich_progress_bar.update(
            self.task_id,
            description=self.song.display_name,
            process_id=str(self.download_id),
            message=message,
            completed=self.progress,
        )

        # If task is complete
        if self.progress == 100 or message == "Error":
            self.parent.overall_completed_tasks += 1
            if self.parent.is_legacy:
                self.parent.rich_progress_bar.remove_task(self.task_id)

        # Update the overall progress bar
        self.parent.overall_progress += delta
        self.parent.update_overall()

        self.old_progress = self.progress
