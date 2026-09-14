"""Minimal .env loader shared by every CLI in this distribution.

Standard library only - no python-dotenv dependency. The wrappers (``ghl``,
``ghl.cmd``) do no .env parsing at all; this module owns it.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

__all__ = ["load_dotenv"]

_LINE_SPLIT_RE = re.compile(r"\r\n|\r|\n")

# An inline comment starts at a '#' preceded by at least one space or tab.
_INLINE_COMMENT_RE = re.compile(r"[ \t]#")


def _default_env_path() -> Path:
    """The .env this distribution reads by default.

    Order:
      1. ``GHL_ENV_FILE`` environment variable, if set (used verbatim).
      2. ``.env`` beside the project root - the directory two levels above
         this file, which is the repo root for a source checkout or an
         editable install (``pip install -e .``).
      3. ``.env`` in the current working directory - the fallback for a
         normal (non-editable) install, where step 2 lands inside
         site-packages and no .env can live there.
    """
    override = os.environ.get("GHL_ENV_FILE", "").strip()
    if override:
        return Path(override)

    project_root_env = Path(__file__).resolve().parent.parent / ".env"
    if project_root_env.is_file():
        return project_root_env

    return Path.cwd() / ".env"


def load_dotenv(path: str | os.PathLike | None = None, *, override: bool = False) -> int:
    """Load KEY=VALUE pairs from a .env file into os.environ.

    Returns the number of variables set. Missing file is not an error
    (returns 0). Never raises on a malformed line and never prints.
    """
    try:
        env_path = Path(path) if path is not None else _default_env_path()
        raw = env_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return 0

    count = 0
    for index, line in enumerate(_LINE_SPLIT_RE.split(raw)):
        if index == 0:
            line = line.lstrip("﻿")

        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("export ") or stripped.startswith("export\t"):
            stripped = stripped[len("export"):].lstrip()

        if "=" not in stripped:
            continue

        key, _, value = stripped.partition("=")
        key = key.strip()
        if not key:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            # Quoted value: everything inside the matching quotes is
            # literal. Anything after the closing quote is ignored.
            value = value[1:-1]
        else:
            # Unquoted value: an inline comment starts at the first '#'
            # preceded by whitespace. A '#' glued to the value is part
            # of it (e.g. abc#def, or a value that is entirely #foo).
            match = _INLINE_COMMENT_RE.search(value)
            if match is not None:
                value = value[: match.start()]
            value = value.rstrip()

        if not override and key in os.environ:
            continue

        try:
            os.environ[key] = value
        except (ValueError, TypeError):
            continue
        count += 1

    return count
