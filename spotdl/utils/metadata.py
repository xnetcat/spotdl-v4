import base64

from pathlib import Path
from urllib.request import urlopen

from mutagen.oggopus import OggOpus
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import Picture, FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.easyid3 import EasyID3, ID3
from mutagen.id3 import APIC as AlbumCover, USLT

from spotdl.types import Song


# Apple has specific tags - see mutagen docs -
# http://mutagen.readthedocs.io/en/latest/api/mp4.html
M4A_TAG_PRESET = {
    "album": "\xa9alb",
    "artist": "\xa9ART",
    "date": "\xa9day",
    "title": "\xa9nam",
    "year": "\xa9day",
    "originaldate": "purd",
    "comment": "\xa9cmt",
    "group": "\xa9grp",
    "writer": "\xa9wrt",
    "genre": "\xa9gen",
    "tracknumber": "trkn",
    "albumartist": "aART",
    "discnumber": "disk",
    "cpil": "cpil",
    "albumart": "covr",
    "encodedby": "\xa9too",
    "copyright": "cprt",
    "tempo": "tmpo",
    "lyrics": "\xa9lyr",
    "explicit": "rtng",
}

TAG_PRESET = {key: key for key in M4A_TAG_PRESET}


def _set_id3_mp3(output_file: Path, song: Song, lyrics: str = ""):
    audio_file = EasyID3(str(output_file.resolve()))

    audio_file = _embed_mp3_metadata(audio_file, song)
    audio_file.save(v2_version=3)

    audio_file = _embed_mp3_cover(output_file, song)
    audio_file = _embed_mp3_lyrics(audio_file, lyrics)

    audio_file.save(v2_version=3)


def _set_id3_m4a(output_file: Path, song: Song, lyrics: str = ""):
    audio_file = MP4(str(output_file.resolve()))

    audio_file = _embed_basic_metadata(audio_file, song, "m4a", M4A_TAG_PRESET)
    audio_file = _embed_m4a_metadata(audio_file, song, lyrics)

    audio_file.save()


def _set_id3_flac(output_file: Path, song: Song, lyrics: str = ""):
    audio_file = FLAC(str(output_file.resolve()))

    audio_file = _embed_basic_metadata(audio_file, song, "flac")
    audio_file = _embed_ogg_metadata(audio_file, song, lyrics)
    audio_file = _embed_cover(audio_file, song, "flac")

    audio_file.save()


def _set_id3_opus(output_file: Path, song: Song, lyrics: str = ""):
    audio_file = OggOpus(str(output_file.resolve()))

    audio_file = _embed_basic_metadata(audio_file, song, "opus")
    audio_file = _embed_ogg_metadata(audio_file, song, lyrics)
    audio_file = _embed_cover(audio_file, song, "opus")

    audio_file.save()


def _set_id3_ogg(output_file: Path, song: Song, lyrics: str = ""):
    audio_file = OggVorbis(str(output_file.resolve()))

    audio_file = _embed_basic_metadata(audio_file, song, "ogg")
    audio_file = _embed_ogg_metadata(audio_file, song, lyrics)
    audio_file = _embed_cover(audio_file, song, "ogg")

    audio_file.save()


def _embed_mp3_metadata(audio_file, song: Song):
    audio_file.delete()

    audio_file["title"] = song.name
    audio_file["titlesort"] = song.name
    audio_file["tracknumber"] = [song.track_number, song.tracks_count]
    audio_file["discnumber"] = [song.disc_number, song.disc_count]
    audio_file["artist"] = song.artists
    audio_file["album"] = song.album_name
    audio_file["albumartist"] = song.artists
    audio_file["date"] = song.date
    audio_file["originaldate"] = song.date
    audio_file["encodedby"] = song.publisher
    audio_file["copyright"] = song.copyright

    genres = song.genres
    if len(genres) > 0:
        audio_file["genre"] = genres[0]

    return audio_file


def _embed_mp3_cover(file_path, song: Song):
    audio_file = ID3(file_path)
    if song.cover_url:
        with urlopen(song.cover_url) as raw_album_art:
            audio_file["APIC"] = AlbumCover(
                encoding=3,
                mime="image/jpeg",
                type=3,
                desc="Cover",
                data=raw_album_art.read(),
            )

    return audio_file


def _embed_mp3_lyrics(audio_file, lyrics: str = ""):
    uslt_output = USLT(encoding=3, lang="eng", desc="desc", text=lyrics)
    audio_file["USLT::'eng'"] = uslt_output

    return audio_file


def _embed_m4a_metadata(audio_file, song: Song, lyrics: str = ""):
    audio_file[M4A_TAG_PRESET["year"]] = str(song.year)
    audio_file[M4A_TAG_PRESET["lyrics"]] = lyrics
    audio_file[M4A_TAG_PRESET["explicit"]] = (4 if song.explicit is True else 2,)

    if song.cover_url:
        try:
            with urlopen(song.cover_url) as raw_album_art:
                audio_file[M4A_TAG_PRESET["albumart"]] = [
                    MP4Cover(
                        raw_album_art.read(),
                        imageformat=MP4Cover.FORMAT_JPEG,
                    )
                ]
        except IndexError:
            pass

    return audio_file


def _embed_basic_metadata(audio_file, song: Song, encoding, preset=TAG_PRESET):
    album_name = song.album_name
    if album_name:
        audio_file[preset["album"]] = album_name

    audio_file[preset["artist"]] = song.artist
    audio_file[preset["albumartist"]] = song.artist
    audio_file[preset["title"]] = song.name
    audio_file[preset["date"]] = song.date
    audio_file[preset["originaldate"]] = song.date
    audio_file[preset["genre"]] = song.genres[0]
    audio_file[preset["copyright"]] = song.copyright

    if encoding in ["flac", "ogg", "opus"]:
        zfilled_disc_number = str(song.disc_number).zfill(len(str(song.disc_count)))
        audio_file[preset["discnumber"]] = zfilled_disc_number
    else:
        audio_file[preset["discnumber"]] = [(song.disc_number, song.disc_count)]

    if encoding in ["flac", "ogg", "opus"]:
        zfilled_track_number = str(song.track_number).zfill(len(str(song.tracks_count)))
        audio_file[preset["tracknumber"]] = zfilled_track_number
    else:
        audio_file[preset["tracknumber"]] = [(song.track_number, song.tracks_count)]

    if encoding == "m4a":
        audio_file[preset["encodedby"]] = song.publisher

    return audio_file


def _embed_ogg_metadata(audio_file, song: Song, lyrics: str = ""):
    audio_file["year"] = str(song.year)
    audio_file["lyrics"] = lyrics

    return audio_file


def _embed_cover(audio_file, song: Song, encoding: str):
    if song.cover_url is None:
        return audio_file

    image = Picture()
    image.type = 3
    image.desc = "Cover"
    image.mime = "image/jpeg"

    with urlopen(song.cover_url) as raw_album_art:
        image.data = raw_album_art.read()

    if encoding == "flac":
        audio_file.add_picture(image)
    elif encoding in ["ogg", "opus"]:
        image_data = image.write()
        encoded_data = base64.b64encode(image_data)
        vcomment_value = encoded_data.decode("ascii")
        audio_file["metadata_block_picture"] = [vcomment_value]

    return audio_file


AVAILABLE_FORMATS = {
    "mp3": _set_id3_mp3,
    "flac": _set_id3_flac,
    "opus": _set_id3_opus,
    "ogg": _set_id3_ogg,
    "m4a": _set_id3_m4a,
}


def embed_metadata(
    output_file: Path, song: Song, file_format: str, lyrics: str = ""
) -> None:
    """
    Embeds metadata into the output file.
    """

    function = AVAILABLE_FORMATS.get(file_format)
    if function:
        function(output_file, song, lyrics)
