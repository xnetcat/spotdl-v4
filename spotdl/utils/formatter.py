import re

from typing import List, Optional
from pathlib import Path
from spotdl.types import Song


def create_song_title(song_name: str, song_artists: List[str]) -> str:
    """
    Create the song title.
    """

    joined_artists = ", ".join(song_artists)
    if len(song_artists) >= 1:
        return f"{joined_artists} - {song_name}"

    return song_name


def sanitize_string(string: str) -> str:
    """
    Sanitize the filename to be used in the file system.
    """

    output = string

    # this is windows specific (disallowed chars)
    output = "".join(char for char in output if char not in "/?\\*|<>")

    # double quotes (") and semi-colons (:) are also disallowed characters but we would
    # like to retain their equivalents, so they aren't removed in the prior loop
    output = output.replace('"', "'").replace(":", "-")

    return output


def create_file_name(
    song: Song, template: str, file_extension: str, short: bool = False
) -> Path:
    """
    Create the file name for the song.
    Replace template variables with the actual values.
    """

    artists = ", ".join(song.artists)

    formats = {
        "{title}": song.name,
        "{artists}": song.artists[0] if short is True else artists,
        "{artist}": song.artists[0],
        "{album}": song.album_name,
        "{album-artist}": song.album_artist,
        "{genre}": song.genres[0] if len(song.genres) > 0 else "",
        "{disc-number}": song.disc_number,
        "{disc-count}": song.disc_count,
        "{duration}": song.duration,
        "{year}": song.year,
        "{original-date}": song.date,
        "{track-number}": song.track_number,
        "{tracks-count}": song.tracks_count,
        "{isrc}": song.isrc,
        "{track-id}": song.song_id,
        "{output-ext}": file_extension,
    }

    # If template does not contain any of the keys,
    # append {artists} - {title}.{output-ext} to it
    if not any(key in template for key in formats):
        template += "/{artists} - {title}.{output-ext}"

    # If template ends with a slash. Does not have a file name with extension
    # at the end of the template, append {artists} - {title}.{output-ext} to it
    if template.endswith("/") or template.endswith(r"\\") or template.endswith("\\\\"):
        template += "/{artists} - {title}.{output-ext}"

    # If template does not end with {output-ext}, append it to the end of the template
    if not template.endswith(".{output-ext}"):
        template += ".{output-ext}"

    # sanitize the values in formats dict
    for key, value in formats.items():
        formats[key] = sanitize_string(str(value))

    # Replace all the keys with the values
    for key, value in formats.items():
        template = template.replace(key, str(value))

    # Parse template as Path object
    file = Path(template)

    santitized_parts = []
    for part in file.parts:
        match = re.search(r"[^\.*](.*)[^\.*$]", part)
        if match:
            santitized_parts.append(match.group(0))
        else:
            santitized_parts.append(part)

    # Join the parts of the path
    file = Path(*santitized_parts)

    # Check if the file name length is greater than 255
    if len(file.name) > 255:
        return create_file_name(song, template, file_extension, short=True)

    return file


def parse_duration(duration: Optional[str]) -> float:
    """
    Convert string value of time (duration: "25:36:59") to a float value of seconds (92219.0)
    """

    if duration is None:
        return 0.0

    try:
        # {(1, "s"), (60, "m"), (3600, "h")}
        mapped_increments = zip([1, 60, 3600], reversed(duration.split(":")))
        seconds = sum(multiplier * int(time) for multiplier, time in mapped_increments)
        return float(seconds)

    # This usually occurs when the wrong string is mistaken for the duration
    except (ValueError, TypeError, AttributeError):
        return 0.0
