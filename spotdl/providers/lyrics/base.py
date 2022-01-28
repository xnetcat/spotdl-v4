from typing import List, Optional


class LyricsProvider:
    def __init__(self):
        """
        Base class for all lyrics providers
        """
        self.headers = {
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="91", "Chromium";v="91"',
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36",
            "Accept": "*/*",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Accept-Language": "en-US;q=0.8,en;q=0.7",
        }

    def get_lyrics(self, name: str, artists: List[str]) -> Optional[str]:
        """
        Returns the lyrics for the given song.
        """
        raise NotImplementedError
