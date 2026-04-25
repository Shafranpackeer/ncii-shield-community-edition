"""Minimal async file wrapper used when aiofiles is not installed."""

import builtins


class _AsyncFile:
    def __init__(self, path, mode):
        self.path = path
        self.mode = mode
        self._file = None

    async def __aenter__(self):
        self._file = builtins.open(self.path, self.mode)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._file.close()

    async def write(self, data):
        return self._file.write(data)


def open(path, mode="r"):
    return _AsyncFile(path, mode)
