"""Session id helpers for file-marked messages."""

import hashlib
import re
from pathlib import PurePath
from typing import Optional


FILENAME_MARKER_PATTERN = re.compile(r"@@([^@]+)@@")


def extract_session_id_from_message(message: str) -> Optional[str]:
    """Extract a stable file-based session id from a message marker."""
    if not message:
        return None

    match = FILENAME_MARKER_PATTERN.search(message)
    if not match:
        return None

    filename = match.group(1).strip()
    if not filename:
        return None

    stem = PurePath(filename).stem
    digest = hashlib.sha256(stem.encode("utf-8")).hexdigest()[:16]
    return f"file_{digest}"


def remove_filename_markers(message: str) -> str:
    """Remove file markers from a message while preserving marker-only input."""
    if not message:
        return message

    clean_message = FILENAME_MARKER_PATTERN.sub("", message).strip()
    if not clean_message:
        return message

    return clean_message

