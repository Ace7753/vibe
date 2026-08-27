from ..utils import VotiyException


class VotifyDownloaderException(VotiyException):
    pass


class VotifyMediaFileExists(VotifyDownloaderException):
    def __init__(self, media_path: str):
        super().__init__(f"Media file already exists at path: {media_path}")

        self.media_path = media_path


class VotifyDependencyNotFound(VotifyDownloaderException):
    def __init__(self, dependency: str):
        super().__init__(f"Dependency not found: {dependency}")

        self.dependency = dependency


class VotifySyncedLyricsOnly(VotifyDownloaderException):
    def __init__(self):
        super().__init__("Only downloading synced lyrics is supported")
