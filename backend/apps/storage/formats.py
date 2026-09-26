"""The file types an upload may be, and how each is recognised on disk.

A type is accepted only if its first bytes match: the declared Content-Type is
never trusted on its own. Anything a browser could run (HTML, SVG, XML,
JavaScript) is deliberately absent, since the files are served from our domain.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Format:
    extension: str
    # (offset, bytes) pairs that must all match.
    signature: tuple[tuple[int, bytes], ...]

    def matches(self, head: bytes) -> bool:
        return all(head[offset : offset + len(magic)] == magic for offset, magic in self.signature)


FORMATS = {
    "image/jpeg": Format("jpg", ((0, b"\xff\xd8\xff"),)),
    "image/png": Format("png", ((0, b"\x89PNG\r\n\x1a\n"),)),
    "image/gif": Format("gif", ((0, b"GIF8"),)),
    "image/webp": Format("webp", ((0, b"RIFF"), (8, b"WEBP"))),
    "image/avif": Format("avif", ((4, b"ftypavi"),)),
    "application/pdf": Format("pdf", ((0, b"%PDF-"),)),
}

# Enough bytes to check every signature above.
HEAD_SIZE = 16
