"""Release version ordering.

Store version strings are loosely semver ("2.3", "2.3.1", "2.3.1 (412)"), so we
parse the leading numeric components and ignore build suffixes. Lexical sorting
would put "2.10.0" before "2.9.0", which silently breaks N vs N-1 comparisons.
"""

import re
from collections.abc import Iterable

_VERSION_RE = re.compile(r"^\s*v?(\d+(?:\.\d+){0,3})")


def version_key(version: str) -> tuple[int, ...]:
    match = _VERSION_RE.match(version)
    if match is None:
        return ()
    parts = [int(p) for p in match.group(1).split(".")]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def normalize_version(version: str | None) -> str | None:
    if version is None:
        return None
    match = _VERSION_RE.match(version)
    return match.group(1) if match else None


def sort_versions(versions: Iterable[str]) -> list[str]:
    return sorted({v for v in versions if version_key(v)}, key=version_key)


def previous_version(versions: Iterable[str], version: str) -> str | None:
    """The release immediately before `version` among the versions we have data for."""
    ordered = sort_versions(versions)
    target = version_key(version)
    earlier = [v for v in ordered if version_key(v) < target]
    return earlier[-1] if earlier else None
