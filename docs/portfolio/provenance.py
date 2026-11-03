"""Use Git's LF text convention so provenance survives Windows/Linux checkouts."""

import hashlib

TEXT_SUFFIXES = {".json", ".csv", ".md", ".py", ".mjs", ".ps1", ".toml", ".lock"}


def source_digest(path):
    data = path.read_bytes()
    if path.suffix in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()
