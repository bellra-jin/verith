"""Selective Google input reader for a future, explicitly approved login launcher.

Importing or running this module never reads a private file or starts a process.
Call read_google_inputs only after the specific file-read/credential-use action is
approved. Never merge a parsed dotenv file or the parent's environment into apps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
import os
from pathlib import Path
import re
import stat

from dotenv.parser import parse_stream

_KEYS = frozenset({"GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"})
_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


class GoogleInputError(ValueError):
    def __init__(self) -> None:
        super().__init__(
            "Two unique, nonempty literal Google client settings are required"
        )


@dataclass(frozen=True)
class GoogleInputs:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)

    def backend_environment(self) -> dict[str, str]:
        """For the approved Backend child only; never log this dictionary."""
        return {
            "GOOGLE_CLIENT_ID": self.client_id,
            "GOOGLE_CLIENT_SECRET": self.client_secret,
        }


def _single_line_literal(raw: str) -> bool:
    # Syntax state only: never decode/store non-target assignment values.
    value = raw.lstrip(" \t").rstrip("\r\n")
    if not value or value.startswith("#"):
        return True
    if value[0] not in ("'", '"'):
        return "'" not in value and '"' not in value and not value.endswith("\\")
    quote, escaped = value[0], False
    for index, character in enumerate(value[1:], 1):
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == quote:
            remaining = value[index + 1 :].strip()
            return not remaining or remaining.startswith("#")
    return False


def read_google_inputs(path: Path) -> GoogleInputs:
    """Scan assignments, parse only the two Google keys, never interpolate/fallback.

    Non-Google values are not parsed, copied, exported, validated or returned.
    Existing DATABASE_URL and all other secrets/configuration remain unrelated.
    Only single-line literal values are accepted; malformed/duplicate values fail
    without exposing the rejected line, input, path or underlying exception.
    """
    values: dict[str, str] = {}
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 1_048_576:
            raise GoogleInputError()
        with os.fdopen(descriptor, encoding="utf-8") as source:
            descriptor = None
            for line in source:
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                assignment = _ASSIGNMENT.match(line)
                # Reject quoted/ambiguous keys and any multiline assignment before
                # a key-looking line can be misinterpreted as a new assignment.
                if assignment is None or not _single_line_literal(
                    line[assignment.end() :]
                ):
                    raise GoogleInputError()
                if assignment[1] not in _KEYS:
                    continue
                name = assignment[1]
                if name in values:
                    raise GoogleInputError()
                bindings = list(parse_stream(StringIO(line)))
                if len(bindings) != 1:
                    raise GoogleInputError()
                binding = bindings[0]
                value = binding.value
                if (
                    binding.error
                    or binding.key != name
                    or not value
                    or not value.strip()
                    or len(value) > 4096
                    or any(char in value for char in ("\x00", "\n", "\r"))
                    or "${" in value
                ):
                    raise GoogleInputError()
                values[name] = value
        if set(values) != _KEYS:
            raise GoogleInputError()
        return GoogleInputs(values["GOOGLE_CLIENT_ID"], values["GOOGLE_CLIENT_SECRET"])
    except (OSError, UnicodeError, ValueError):
        raise GoogleInputError() from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(
        "Preparation library only: no credential file read or login action is executed"
    )
