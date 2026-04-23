"""Path utility functions for safe WebDAV path handling."""

import posixpath
from urllib.parse import quote


def sanitize_webdav_path(path: str) -> str:
    """Sanitize and percent-encode a WebDAV path.

    Normalizes the path, rejects directory traversal, and percent-encodes
    non-ASCII and special characters so that Unicode filenames (e.g. Japanese)
    are correctly transmitted over WebDAV.

    Args:
        path: User-provided file/directory path.

    Returns:
        Normalized, percent-encoded path without leading slash.

    Raises:
        ValueError: If path contains '..' traversal components.
    """
    if not path or path.strip("/") == "":
        return ""
    normalized = posixpath.normpath(path)
    if ".." in normalized.split("/"):
        raise ValueError(f"Path traversal detected: {path!r}")
    return quote(normalized.lstrip("/"), safe="/")
