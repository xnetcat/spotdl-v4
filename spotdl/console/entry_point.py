import sys
import json
import logging

from spotdl.console.save import save
from spotdl.download import Downloader
from spotdl.console.preload import preload
from spotdl.console.download import download
from spotdl.utils.config import DEFAULT_CONFIG
from spotdl.utils.ffmpeg import download_ffmpeg
from spotdl.utils.config import get_config_file
from spotdl.utils.arguments import parse_arguments
from spotdl.utils.spotify import SpotifyClient, SpotifyError
from spotdl.download.progress_handlers.base import NAME_TO_LEVEL
from spotdl.download.downloader import DownloaderError, PROGRESS_HANDLERS


def console_entry_point():
    """
    Console entry point for spotdl. This is where the magic happens.
    """

    # Don't log too much
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("spotipy").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Download ffmpeg if the `--download-ffmpeg` flag is passed
    # This is done before the argument parser so it doesn't require `operation`
    # and `query` to be passed. Exit after downloading ffmpeg
    if "--download-ffmpeg" in sys.argv:
        download_ffmpeg()

        return None

    # Generate the config file if it doesn't exist
    # or overwrite the current config file if the `--overwrite-config` flag is passed
    # This is done before the argument parser so it doesn't requires `operation`
    # and `query` to be passed. exit after downloading ffmpeg
    if "--generate-config" in sys.argv:
        config_path = get_config_file()
        with open(config_path, "w", encoding="utf-8") as config_file:
            json.dump(DEFAULT_CONFIG, config_file, indent=4)

        return None

    # Parse the arguments
    arguments = parse_arguments()

    # Get the config file
    config = {}
    if arguments.config:
        # Load the config file
        with open(get_config_file(), "r", encoding="utf-8") as config_file:
            config = json.load(config_file)

    # Create settings dict
    # Settings from config file will override the ones from the command line
    settings = {}
    for key in DEFAULT_CONFIG:
        if config.get(key) is None:
            settings[key] = arguments.__dict__[key]
        else:
            settings[key] = config[key]

    progress_handler_class = PROGRESS_HANDLERS.get(settings["progress_handler"])
    progress_handler = (
        progress_handler_class(
            log_level=NAME_TO_LEVEL["DEBUG"]
            if settings["verbose"]
            else NAME_TO_LEVEL["INFO"],
        )
        if progress_handler_class
        else None
    )

    if arguments.query and "saved" in arguments.query and not settings["user_auth"]:
        raise SpotifyError("You must be logged in to use the saved query.")

    # Initialize spotify client
    SpotifyClient.init(
        client_id=settings["client_id"],
        client_secret=settings["client_secret"],
        user_auth=settings["user_auth"],
    )

    if arguments.operation in ["download", "preload"]:
        if arguments.operation == "preload":
            if not settings["save_file"].endswith(".spotdl"):
                raise DownloaderError("Save file has to end with .spotdl")

        # Initialize the downloader
        # for download, load and preload operations
        downloader = Downloader(
            audio_provider=settings["audio_provider"],
            lyrics_provider=settings["lyrics_provider"],
            ffmpeg=settings["ffmpeg"],
            variable_bitrate=settings["variable_bitrate"],
            constant_bitrate=settings["constant_bitrate"],
            ffmpeg_args=settings["ffmpeg_args"],
            output_format=settings["format"],
            save_file=settings["save_file"],
            threads=settings["threads"],
            output=settings["output"],
            overwrite=settings["overwrite"],
            m3u_file=settings["m3u"],
            progress_handler=progress_handler,  # type: ignore
        )

        if arguments.operation == "download":
            download(arguments.query, downloader=downloader)
        elif arguments.operation == "preload":
            preload(
                query=arguments.query,
                save_path=settings["save_file"],
                downloader=downloader,
            )
    elif arguments.operation == "save":
        # Save the songs to a file
        save(
            query=arguments.query,
            save_path=settings["save_file"],
            threads=settings["threads"],
        )
    elif arguments.operation == "web":
        pass

    return None
